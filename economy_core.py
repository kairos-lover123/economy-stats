"""Economy Studio: auditable, read-only economy analytics and DHT importing.

All analysis is derived from balance-update events. This is not a bank ledger or
an account-balance snapshot. No writes are made to user-supplied databases.
"""
from __future__ import annotations

import csv
from contextlib import closing
import datetime as dt
import hashlib
import json
import math
import mmap
import os
import re
import sqlite3
import statistics
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

APP_DIR = Path(os.environ.get('LOCALAPPDATA') or (Path.home() / '.economy_studio')) / 'EconomyStudio'
MAX_CHANGE = 1_000_000
# SQLite accepts only signed 64-bit values as bound Python integers. Discord
# audit descriptions can contain arbitrarily large numbers (bad logs, balances
# in other systems, or corrupted records). Never bind such a number directly.
SQLITE_MIN_INTEGER = -(1 << 63)
SQLITE_MAX_INTEGER = (1 << 63) - 1
INDEX_FORMAT_VERSION = 3


def sqlite_integer_or_none(value):
    """Return a bindable SQLite integer, or NULL for an out-of-range value.

    The precise original number is retained separately as text in the index,
    and always remains available inside the original read-only DHT record.
    """
    return value if SQLITE_MIN_INTEGER <= value <= SQLITE_MAX_INTEGER else None

USER_RE = re.compile(r'\*\*User:\*\*\s*<@!?(\d+)>', re.I)
CASH_RE = re.compile(r'Cash:\s*`?\s*([+-]?[\d, ]+)', re.I)
BANK_RE = re.compile(r'Bank:\s*`?\s*([+-]?[\d, ]+)', re.I)
REASON_RE = re.compile(r'\*\*Reason:\*\*\s*(.*)', re.I | re.S)
SHOP_RE = re.compile(r'^buy\s+item\s*\(\s*(.*?)\s*\)\s*$', re.I)
MAFIA_SHOP_RE = re.compile(r'^mafia\s+profile\s+shop\s+purchase:\s*(.*?)\s*\(([^()]*)\)\s*$', re.I)
ANIMAL_RE = re.compile(r'^buy\s+animal(?:\s+command)?\s*\(\s*(.*)\s*\)\s*$', re.I)
PROVISION_RE = re.compile(r'^buy\s+provision(?:\s+command)?\s*\(\s*(.*)\s*\)\s*$', re.I)
ROLE_RE = re.compile(r'role\s+income\s+for\s+<@&(\d+)>', re.I)
CHANNEL_RE = re.compile(r'chat\s+money\s+in\s+<#(\d+)>', re.I)
JSON_BEGIN = re.compile(rb'\{"author":')
DEFAULT_FILTERS = {'exclude_transfers': True, 'exclude_admin': True, 'include_invalid': False}

# A consistent game catalogue keeps every recognized casino game visible,
# including games with no transactions in the selected reporting interval.
GAME_NAMES = ('Blackjack', 'Cockfight', 'Roulette', 'Russian Roulette',
              'Slot Machine', 'Higher or Lower', 'Animal Race')


def number(value):
    try:
        return int(str(value).replace(',', '').replace(' ', '').replace('`',''))
    except (ValueError, TypeError):
        return 0


def timestamp(value):
    try:
        val = str(value).strip().replace('Z', '+00:00')
        parsed = dt.datetime.fromisoformat(val)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    except (TypeError, ValueError):
        return None


def utc_display(s):
    if not s:
        return ''
    try:
        date = dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
        return date.astimezone().strftime('%Y-%m-%d %H:%M')
    except ValueError:
        return str(s)


def clean_text(value):
    value = re.sub(r'\s+', ' ', str(value))
    return value.strip()


def shop_name(value):
    return re.sub(r'^(?:\d+\s*[.)]\s*)+', '', clean_text(value)).strip()


def slug(value):
    return re.sub(r'\s+', ' ', str(value).strip()).casefold()


@dataclass(frozen=True)
class Kind:
    domain: str
    source: str
    component: str = 'other'
    item_group: str = ''
    item_id: str = ''
    item: str = ''


def classify(raw_reason):
    """Hierarchical source/item taxonomy, based on actual exported reason strings."""
    reason = clean_text(raw_reason)
    plain = re.sub(r'^api patch:\s*', '', reason, flags=re.I)
    low = plain.casefold()

    mafia = MAFIA_SHOP_RE.match(plain)
    if mafia:
        item, item_id = mafia.group(1).strip(), mafia.group(2).strip()
        key = item_id.casefold()
        if key.startswith('role-voucher') or key.startswith('voucher-'): group = 'Vouchers'
        elif key.startswith('token-'): group = 'Tokens'
        elif key.startswith('death-'): group = 'Death messages'
        elif key.startswith('voted-'): group = 'Voting messages'
        elif key.startswith('custom-'):
            if 'background' in key: group = 'Backgrounds'
            elif 'gradient' in key: group = 'Gradients'
            elif 'frame' in key: group = 'Frames'
            elif 'bundle' in key: group = 'Bundles'
            elif 'color' in key: group = 'Colors'
            elif 'gif' in key: group = 'Kill GIFs'
            else: group = 'Custom orders'
        else:
            prefixes = [('color-','Colors'),('gradient-','Gradients'),('background-','Backgrounds'),('frame-','Frames'),('bundle-','Bundles'),('title-','Titles'),('badge-','Badges')]
            group = next((name for prefix, name in prefixes if key.startswith(prefix)), 'Other Mafia items')
        return Kind('Shops', 'Mafia profile shop', 'purchase', group, item_id, item)

    match = SHOP_RE.match(plain)
    if match:
        name = shop_name(match.group(1))
        if name.casefold() == 'chicken':
            return Kind('Games', 'Cockfight', 'inventory cost', 'Game supplies', 'chicken', 'Chicken')
        return Kind('Shops', 'Regular item shop', 'purchase', 'Regular items', slug(name), name)

    animal = ANIMAL_RE.match(plain)
    if animal:
        val = animal.group(1).strip()
        types = re.findall(r'\((Horse|Snail|Greyhound|Pigeon)\)', val, re.I)
        typ = types[-1].title() if types else (val.title() if val.casefold() in {'horse','snail','greyhound','pigeon'} else 'Other animal')
        return Kind('Games', 'Animal Race', 'animal cost', 'Animals', slug(typ), typ)
    provision = PROVISION_RE.match(plain)
    if provision:
        name = clean_text(provision.group(1))
        return Kind('Games', 'Animal Race', 'provision cost', 'Provisions', slug(name), name)

    games = [
        ('slot-machine', 'Slot Machine'), ('slot machine', 'Slot Machine'),
        ('blackjack', 'Blackjack'), ('cock-fight', 'Cockfight'),
        ('cockfight', 'Cockfight'), ('chicken-fight', 'Cockfight'),
        ('russian-roulette', 'Russian Roulette'), ('russian roulette', 'Russian Roulette'),
        ('higher-lower', 'Higher or Lower'), ('higher lower', 'Higher or Lower'),
        ('higher or lower', 'Higher or Lower'), ('animal-race', 'Animal Race'),
        ('animal race', 'Animal Race'), ('roulette', 'Roulette'),
    ]
    for prefix, name in games:
        if low.startswith(prefix):
            if ' bet' in low or low.endswith('bet'): component = 'stake'
            elif any(v in low for v in ('win','won','payout','ended','return bet')): component = 'payout'
            else: component = 'other game event'
            return Kind('Games', name, component)

    if low.startswith(('paid mafia wager', 'ranked mafia entry bet')):
        return Kind('Mafia', 'Mafia matches', 'stake')
    if ('mafia' in low and 'refund' in low and any(s in low for s in ('lobby','wager','failed-start','unresolved-player','stopped-game','idle-lobby'))):
        return Kind('Mafia', 'Mafia matches', 'refund')
    if low.startswith('mafia match cash payout'):
        return Kind('Mafia', 'Mafia matches', 'match payout')
    if low.startswith('mafia performance reward'):
        return Kind('Mafia', 'Mafia matches', 'performance reward')
    if low.startswith('mafia hosting deposit'):
        return Kind('Mafia', 'Mafia hosting', 'deposit')
    if 'hosting deposit refund' in low:
        return Kind('Mafia', 'Mafia hosting', 'deposit refund')
    if low.startswith(('mafia host shop reward', 'mafia hosting reward')):
        return Kind('Mafia', 'Mafia hosting', 'hosting reward')
    if low.startswith('mafia quest rewards'):
        m = re.search(r'\(([^)]*)\)', low)
        what = (m.group(1) if m else 'general').replace('_',' ').title()
        return Kind('Mafia', 'Mafia quests', what)
    if 'mafia' in low and 'host' in low and 'refund' in low:
        return Kind('Mafia', 'Mafia hosting', 'refund')

    m = ROLE_RE.search(plain)
    if m:
        return Kind('Earnings', 'Role income', 'role payout', 'Roles', m.group(1), 'Role ' + m.group(1))
    m = CHANNEL_RE.search(plain)
    if m:
        return Kind('Earnings', 'Chat activity', 'chat payout', 'Channels', m.group(1), 'Channel ' + m.group(1))
    if low.startswith('work command'): return Kind('Earnings', 'Work', 'command reward')
    if low.startswith('crime command'): return Kind('Earnings', 'Crime', 'command result')
    if low.startswith('slut command'): return Kind('Earnings', 'Slut', 'command result')
    if low.startswith(('rob successful','rob fine','robbed')):
        return Kind('Earnings', 'Robbery', 'fine' if 'fine' in low else 'result')
    if low.startswith(('give-money','take-money','transfer')):
        return Kind('Transfers', 'Player transfers', 'transfer')
    if low.startswith(('add-money','remove-money','set-money')):
        return Kind('Adjustments', 'Admin adjustments', 'administrative change')
    return Kind('Unclassified', 'Unclassified', reason or '(no reason)')


def parse_embed(embed):
    desc = embed.get('description', '')
    if not isinstance(desc, str): return None
    user = USER_RE.search(desc)
    cash = CASH_RE.search(desc)
    bank = BANK_RE.search(desc)
    when = timestamp(embed.get('timestamp'))
    if not (user and (cash or bank) and when): return None
    c = number(cash.group(1)) if cash else 0
    b = number(bank.group(1)) if bank else 0
    reason = REASON_RE.search(desc)
    text = clean_text(reason.group(1)) if reason else 'Unknown'
    return when, user.group(1), c, b, c+b, text


def quote(name):
    return '"' + str(name).replace('"', '""') + '"'


class ClosingReadConnection(sqlite3.Connection):
    # sqlite3.Connection's normal context manager commits, but does not close.
    def __exit__(self,exc_type,exc,tb):
        try:return super().__exit__(exc_type,exc,tb)
        finally:self.close()


def readonly_connection(path):
    # URI path avoids creating accidental new databases, and queries cannot alter data.
    uri = Path(path).resolve().as_uri() + '?mode=ro'
    conn = sqlite3.connect(uri, uri=True, timeout=10, factory=ClosingReadConnection)
    conn.execute('PRAGMA query_only=ON')
    return conn


def find_json_column(conn):
    rows = conn.execute('PRAGMA table_info("message_embeds")').fetchall()
    if not rows: raise ValueError('This DHT has no message_embeds table.')
    columns = [r[1] for r in rows]
    for key in ('json','embed_json','data','embed','value','content'):
        for name in columns:
            if name.casefold() == key: return name
    for name in columns:
        try:
            values = conn.execute(f'SELECT {quote(name)} FROM message_embeds WHERE {quote(name)} IS NOT NULL LIMIT 20')
            for (value,) in values:
                if isinstance(value,str) and value.startswith('{'):
                    obj = json.loads(value)
                    if isinstance(obj,dict) and 'description' in obj: return name
        except (sqlite3.Error, ValueError, TypeError): pass
    raise ValueError('The DHT embed JSON column could not be identified.')


def read_user_names(raw_path):
    """Best effort usernames from typical DHT user/member tables."""
    result={}
    try:
        with readonly_connection(raw_path) as conn:
            tables=[r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            for table in tables:
                if 'user' not in table.casefold() and 'member' not in table.casefold():continue
                columns=[r[1] for r in conn.execute('PRAGMA table_info('+quote(table)+')')]
                norm={re.sub(r'[^a-z0-9]','',col.casefold()):col for col in columns}
                ids=next((norm[k] for k in ('discorduserid','userid','discordid','id') if k in norm),None)
                names=next((norm[k] for k in ('username','globalname','displayname','name','nickname','nick') if k in norm),None)
                if not (ids and names):continue
                sql='SELECT '+quote(ids)+','+quote(names)+' FROM '+quote(table)+' WHERE '+quote(ids)+' IS NOT NULL AND '+quote(names)+' IS NOT NULL LIMIT 300000'
                try:
                    for identity,nickname in conn.execute(sql):
                        uid=str(identity).strip();display=str(nickname).strip()
                        if re.fullmatch(r'\d{10,25}',uid) and display and display.casefold() not in ('none','null'):
                            result[uid]=display[:80]
                except sqlite3.Error:continue
    except (sqlite3.Error,OSError):pass
    return result


def shard_signature(paths):
    h=hashlib.sha256()
    for p in sorted(map(Path,paths)):
        stat=p.stat()
        h.update(f'{p.name}|{stat.st_size}|{stat.st_mtime_ns}'.encode())
    return h.hexdigest()[:16]


def shard_parts(paths):
    return sorted({int(m.group(1)) for path in paths if (m:=re.search(r'\.part(\d+)$', Path(path).name, re.I))})


def extract_shards(paths, out_path, progress:Callable | None=None):
    """Recover independent embedded JSON objects. No attempt to fake missing SQLite pages."""
    dest=Path(out_path); dest.parent.mkdir(parents=True,exist_ok=True)
    tmp=dest.with_suffix('.building')
    if tmp.exists(): tmp.unlink()
    conn=sqlite3.connect(tmp)
    count=0; bad=0
    try:
        conn.execute('PRAGMA journal_mode=OFF')
        conn.execute('PRAGMA synchronous=OFF')
        conn.execute('CREATE TABLE message_embeds (id INTEGER PRIMARY KEY, json TEXT NOT NULL)')
        conn.execute('CREATE TABLE economy_studio_origin (key TEXT PRIMARY KEY,value TEXT)')
        for i,path in enumerate(sorted(map(Path,paths))):
            if progress: progress(f'Recovering audit events: {path.name} ({i+1}/{len(paths)})')
            with path.open('rb') as fh:
                with mmap.mmap(fh.fileno(),0,access=mmap.ACCESS_READ) as data:
                    cursor=0
                    for match in JSON_BEGIN.finditer(data):
                        start=match.start()
                        # Audit embeds are small JSON objects. Never consume an entire page blindly.
                        raw=data[start:start+16384]
                        try:
                            end=raw.index(b'}')+1
                            # JSON string values may contain nested objects; raw_decode locates the real end.
                            obj, _ = json.JSONDecoder().raw_decode(raw.decode('utf-8','replace'))
                            if not isinstance(obj,dict) or not parse_embed(obj): continue
                            minimal={'timestamp':obj['timestamp'],'description':obj['description']}
                            conn.execute('INSERT INTO message_embeds(json) VALUES (?)',(json.dumps(minimal,ensure_ascii=False,separators=(',',':')),))
                            count+=1
                        except (ValueError, UnicodeError, KeyError, TypeError, json.JSONDecodeError): bad+=1
                        if count and count % 10000 == 0 and cursor != count:
                            cursor=count
                            conn.commit()
            conn.commit()
        parts=shard_parts(paths)
        origins={'kind':'recovered_fragments','pieces':','.join(map(str,parts)),'missing_first':'1' if parts and min(parts)>1 else '0','recovered_records':str(count),'failed_embeds':str(bad),'files':' | '.join(p.name for p in paths)}
        conn.executemany('INSERT INTO economy_studio_origin VALUES (?,?)',origins.items())
        conn.commit(); conn.close()
        tmp.replace(dest)
        if progress: progress(f'{count:,} usable events recovered')
        return count
    except Exception:
        conn.close()
        try: tmp.unlink()
        except OSError: pass
        raise


class EconomyStore:
    """Indexed analytic snapshot. The input source is never modified."""
    def __init__(self, cache_root=None):
        self.cache_root=Path(cache_root or APP_DIR)
        self.cache_root.mkdir(parents=True,exist_ok=True)
        self.snapshot=None
        self.note=''
        self.stats={}
        self.user_names={}

    def load(self, files, progress:Callable | None=None):
        paths=sorted({Path(f).resolve() for f in files})
        if not paths: raise ValueError('Choose a .dht file or one or more .part### files.')
        for p in paths:
            if not p.is_file(): raise FileNotFoundError(str(p))
        fragments=any(re.search(r'\.part\d+$',p.name,re.I) for p in paths)
        if fragments and not all(re.search(r'\.part\d+$',p.name,re.I) for p in paths):
            raise ValueError('Load a complete .dht separately from .part### fragments.')
        if fragments:
            parts=shard_parts(paths)
            if len(parts)!=len(paths): raise ValueError('Each fragment must have a different .part### number.')
            snapshot_name='fragments_'+shard_signature(paths)
            raw=self.cache_root/(snapshot_name+'.dht')
            if not raw.exists(): extract_shards(paths,raw,progress)
            incomplete=1 not in parts or any(n not in parts for n in range(1,max(parts)+1))
            self.note=('PARTIAL ARCHIVE: pieces '+', '.join(f'{n:03}' for n in parts)+' loaded. '
                       +('Missing pieces, including part001. Totals are not complete.' if incomplete else 'All numbered pieces were supplied; event recovery is best effort.'))
        else:
            if len(paths)!=1: raise ValueError('Select one complete .dht or multiple .part### files.')
            raw=paths[0]
            with raw.open('rb') as f:
                if f.read(16)!=b'SQLite format 3\0': raise ValueError('Not a complete SQLite/DHT database. If split, select all .part### files.')
            self.note='Complete SQLite database opened read-only.'
            with readonly_connection(raw) as check:
                has_origin=check.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='economy_studio_origin'").fetchone()
                if has_origin:
                    meta=dict(check.execute('SELECT key,value FROM economy_studio_origin').fetchall())
                    if meta.get('kind')=='recovered_fragments':
                        self.note='PARTIAL ARCHIVE: recovered audit records from pieces '+meta.get('pieces','unknown')+'. Original SQLite tables and missing earlier pages are unavailable.'
        self.user_names=read_user_names(raw)
        signature=shard_signature(paths)
        indexed=self.cache_root/(f'index_v{INDEX_FORMAT_VERSION}_'+signature+'.sqlite')
        if not indexed.exists(): self._build_index(raw,indexed,progress)
        self.snapshot=indexed
        with self.connect() as conn:
            row=conn.execute('SELECT COUNT(*), MIN(utc), MAX(utc), COUNT(DISTINCT user_id),SUM(invalid) FROM tx').fetchone()
            self.stats={'events':row[0], 'first':row[1], 'last':row[2], 'users':row[3], 'outliers':row[4] or 0}
        if progress: progress('Ready')
        return self.stats

    def _build_index(self, raw, target, progress=None):
        building=target.with_suffix('.building')
        if building.exists(): building.unlink()
        dest=sqlite3.connect(building)
        src=readonly_connection(raw)
        try:
            dest.execute('PRAGMA journal_mode=OFF')
            dest.execute('PRAGMA synchronous=OFF')
            dest.executescript('''
               CREATE TABLE tx(id INTEGER PRIMARY KEY,utc TEXT NOT NULL,user_id TEXT NOT NULL,
               cash INTEGER,bank INTEGER,amount INTEGER,reason TEXT,domain TEXT,source TEXT,
               component TEXT,item_group TEXT,item_id TEXT,item_name TEXT,invalid INTEGER DEFAULT 0,
               cash_exact TEXT,bank_exact TEXT,amount_exact TEXT);
               CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
            ''')
            col=find_json_column(src)
            batch=[]; read=0; ignored=0
            if progress: progress('Indexing events and classifying income sources')
            cur=src.execute(f'SELECT {quote(col)} FROM message_embeds WHERE {quote(col)} IS NOT NULL')
            for (raw_embed,) in cur:
                read+=1
                if not isinstance(raw_embed,str): ignored+=1; continue
                try:
                    parsed=parse_embed(json.loads(raw_embed))
                except (ValueError,TypeError,KeyError): parsed=None
                if not parsed: ignored+=1; continue
                when,user,cash,bank,total,reason=parsed
                kind=classify(reason)
                safe_cash=sqlite_integer_or_none(cash)
                safe_bank=sqlite_integer_or_none(bank)
                safe_total=sqlite_integer_or_none(total)
                out_of_range=(safe_cash is None or safe_bank is None or safe_total is None)
                invalid=int(abs(total)>MAX_CHANGE or out_of_range)
                # Keep full decimal values only for unrepresentable integers;
                # storing them as SQLite INTEGER (even if excluded) would crash.
                batch.append((when,user,safe_cash,safe_bank,safe_total,reason,
                              kind.domain,kind.source,kind.component,kind.item_group,
                              kind.item_id,kind.item,invalid,
                              str(cash) if safe_cash is None else None,
                              str(bank) if safe_bank is None else None,
                              str(total) if safe_total is None else None))
                if len(batch)>=3000:
                    dest.executemany('INSERT INTO tx(utc,user_id,cash,bank,amount,reason,domain,source,component,item_group,item_id,item_name,invalid,cash_exact,bank_exact,amount_exact) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',batch)
                    batch=[]
                    if progress and read%30000<3000: progress(f'Indexed {read:,} audit rows')
            if batch:
                dest.executemany('INSERT INTO tx(utc,user_id,cash,bank,amount,reason,domain,source,component,item_group,item_id,item_name,invalid,cash_exact,bank_exact,amount_exact) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',batch)
            dest.executescript('''
                CREATE INDEX idx_tx_time ON tx(utc);
                CREATE INDEX idx_tx_source ON tx(domain,source);
                CREATE INDEX idx_tx_user ON tx(user_id,utc);
                CREATE INDEX idx_tx_item ON tx(source,item_id);
                CREATE INDEX idx_tx_reason ON tx(reason);
            ''')
            dest.executemany('INSERT INTO meta VALUES (?,?)',[('scanned',str(read)),('skipped',str(ignored)),('created',dt.datetime.now(dt.timezone.utc).isoformat())])
            dest.commit();dest.close();src.close()
            building.replace(target)
        except Exception:
            dest.close();src.close()
            try: building.unlink()
            except OSError: pass
            raise

    def user_label(self,uid):
        return self.user_names.get(str(uid),str(uid))

    def connect(self):
        if not self.snapshot: raise RuntimeError('No database loaded.')
        c=readonly_connection(self.snapshot)
        c.row_factory=sqlite3.Row
        return c

    def where(self, filters=None, alias=''):
        f=filters or {}; pref=alias+'.' if alias else ''
        clauses=[pref+'invalid=0']; args=[]
        if not f.get('exclude_transfers',True): pass
        else: clauses.append(pref+"domain!='Transfers'")
        if f.get('exclude_admin',True): clauses.append(pref+"domain!='Adjustments'")
        if f.get('start'):
            clauses.append(pref+'utc>=?');args.append(f['start'])
        if f.get('end'):
            clauses.append(pref+'utc<=?');args.append(f['end'])
        for key,col in (('domain','domain'),('source','source'),('user','user_id'),('item_id','item_id')):
            if f.get(key):
                clauses.append(pref+col+'=?');args.append(f[key])
        if f.get('reason'):
            clauses.append(pref+'reason=?'); args.append(f['reason'])
        excluded=sorted(set(f.get('excluded_sources',())))
        if excluded:
            clauses.append(pref+'source NOT IN ('+','.join('?' for _ in excluded)+')')
            args.extend(excluded)
        return ' WHERE '+' AND '.join(clauses), args

    def query(self, statement,args=()):
        with self.connect() as c:
            return [dict(row) for row in c.execute(statement,args)]

    def totals(self, filters=None):
        wh,args=self.where(filters)
        row=self.query('SELECT COUNT(*) events,COUNT(DISTINCT user_id) users,'
            'COALESCE(SUM(amount),0) net,COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) minted,'
            'COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) burned '
            'FROM tx'+wh,args)[0]
        first_last=self.query('SELECT MIN(utc) first,MAX(utc) last FROM tx'+wh,args)[0]
        row.update(first_last)
        return row

    def sources(self, filters=None, by='source', limit=2500):
        valid={'domain','source','component','reason','item_group','item_id','item_name','user_id'}
        if by not in valid: raise ValueError('Invalid group')
        wh,args=self.where(filters)
        if by=='item_name': wh += (' AND ' if wh else ' WHERE ') + "item_id!=''"
        rows=self.query(f'''SELECT {quote(by)} name,COUNT(*) events,COUNT(DISTINCT user_id) users,
            COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) minted,
            COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) burned,
            COALESCE(SUM(amount),0) net,
            COUNT(DISTINCT CASE WHEN amount<0 THEN user_id END) spenders
            FROM tx {wh} GROUP BY {quote(by)} ORDER BY ABS(SUM(amount)) DESC LIMIT ?''',(*args,limit))
        return rows

    def source_catalogue(self, filters=None):
        """Return every individual source together with its parent category.

        Grouping by BOTH fields avoids combining identical custom source names
        belonging to different domains. It provides one directly inspectable
        source list independent of the overview's top-N rankings.
        """
        wh, args = self.where(filters)
        return self.query('''SELECT domain, source name, COUNT(*) events,
               COUNT(DISTINCT user_id) users,
               COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) minted,
               COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) burned,
               COALESCE(SUM(amount),0) net
               FROM tx ''' + wh + ''' GROUP BY domain, source
               ORDER BY ABS(SUM(amount)) DESC, domain, source''', args)

    def game_breakdown(self, filters=None):
        """Real observed game cashflows, including bets, wins and supply costs.

        A stake event is used as a proxy for one play only when a logged stake
        exists. Payout records are not assumed to equal individual plays.
        """
        f = dict(filters or {})
        f['domain'] = 'Games'
        wh, args = self.where(f)
        rows = self.query('''SELECT source name, COUNT(*) events, COUNT(DISTINCT user_id) users,
            COALESCE(SUM(amount),0) net,
            COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) minted,
            COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) burned,
            SUM(CASE WHEN component='stake' THEN 1 ELSE 0 END) bets,
            SUM(CASE WHEN component='stake' THEN -amount ELSE 0 END) stakes,
            SUM(CASE WHEN component='payout' THEN 1 ELSE 0 END) winning_events,
            SUM(CASE WHEN component='payout' THEN amount ELSE 0 END) payouts,
            SUM(CASE WHEN component IN ('inventory cost','animal cost','provision cost')
                AND amount<0 THEN -amount ELSE 0 END) extra_costs
            FROM tx ''' + wh + ''' GROUP BY source''', args)
        found = {r['name']: r for r in rows}
        result = []
        for name in GAME_NAMES:
            row = found.pop(name, None) or dict(name=name, events=0, users=0, net=0,
                   minted=0, burned=0, bets=0, stakes=0, winning_events=0,
                   payouts=0, extra_costs=0)
            row['net_per_bet'] = round(row['net'] / row['bets'], 2) if row['bets'] else None
            row['return_pct'] = round(row['payouts'] / row['stakes'] * 100, 2) if row['stakes'] else None
            result.append(row)
        for row in sorted(found.values(), key=lambda r: r['name']):
            row['net_per_bet'] = round(row['net'] / row['bets'], 2) if row['bets'] else None
            row['return_pct'] = round(row['payouts'] / row['stakes'] * 100, 2) if row['stakes'] else None
            result.append(row)
        return result

    def items(self, filters=None, shop='all'):
        f=dict(filters or {})
        wh,args=self.where(f)
        parts=[]
        if shop in ('mafia','regular'):
            parts.append('source=?');args.append('Mafia profile shop' if shop=='mafia' else 'Regular item shop')
        elif shop=='other':
            parts.append("item_group IN ('Animals','Provisions','Game supplies')")
        else:
            parts.append("item_id!='' AND (domain='Shops' OR (domain='Games' AND item_group IN ('Animals','Provisions','Game supplies')))")
        wh+=' AND '+' AND '.join(parts)
        return self.query('''SELECT source,item_group,item_id,MAX(item_name) item_name,
            COUNT(*) purchases,COUNT(DISTINCT user_id) buyers,
            -SUM(CASE WHEN amount<0 THEN amount ELSE 0 END) gross_spend,
            -SUM(amount) net_spend,
            ROUND(-1.0*SUM(amount)/COUNT(*),2) avg_spend,
            MAX(utc) last_purchase
            FROM tx '''+wh+''' GROUP BY source,item_group,item_id
            ORDER BY net_spend DESC''',args)

    def item_users(self, item_id, source, filters=None):
        f=dict(filters or {},item_id=item_id,source=source)
        wh,args=self.where(f)
        return self.query('''SELECT user_id,COUNT(*) purchases,-SUM(amount) spent,
              MAX(utc) last_purchase FROM tx '''+wh+' GROUP BY user_id ORDER BY spent DESC',args)

    def events(self, filters=None, search='',page=0,page_size=200,order='utc DESC'):
        f=filters or {}; wh,args=self.where(f)
        if search.strip():
            term='%'+search.strip()+'%'
            wh+=' AND (reason LIKE ? OR user_id LIKE ? OR item_name LIKE ? OR source LIKE ?)'
            args.extend([term]*4)
        order=order if order in ('utc DESC','utc ASC','amount DESC','amount ASC') else 'utc DESC'
        return self.query(f'''SELECT id,utc,user_id,cash,bank,amount,domain,source,component,item_group,
            item_name,item_id,reason FROM tx {wh} ORDER BY {order} LIMIT ? OFFSET ?''',(*args,page_size,page*page_size))

    def timeseries(self, filters=None, unit='day', by_source=False):
        wh,args=self.where(filters)
        slice_="substr(utc,1,10)" if unit=='day' else "substr(utc,1,7)" if unit=='month' else "substr(utc,1,13)"
        extra=',source' if by_source else ''
        rows=self.query(f'''SELECT {slice_} period {extra},SUM(amount) net,
            SUM(CASE WHEN amount>0 THEN amount ELSE 0 END) minted,
            -SUM(CASE WHEN amount<0 THEN amount ELSE 0 END) burned,
            COUNT(*) events,COUNT(DISTINCT user_id) users FROM tx {wh}
            GROUP BY period {extra} ORDER BY period''',args)
        return rows

    def users(self, filters=None, limit=2500):
        wh,args=self.where(filters)
        return self.query('''SELECT user_id,COUNT(*) events,SUM(amount) net,
            SUM(CASE WHEN amount>0 THEN amount ELSE 0 END) minted,
            -SUM(CASE WHEN amount<0 THEN amount ELSE 0 END) burned,
            COUNT(DISTINCT substr(utc,1,10)) active_days,
            COUNT(DISTINCT substr(utc,1,14) || CAST(CAST(substr(utc,15,2) AS INTEGER)/5 AS TEXT)) active_5m,
            MIN(utc) first,MAX(utc) last FROM tx '''+wh+''' GROUP BY user_id
            ORDER BY net DESC LIMIT ?''',(*args,limit))

    def user_sources(self, user, filters=None):
        return self.sources(dict(filters or {},user=user))

    def suspicious_activity(self, filters=None, min_streak=288):
        f=dict(filters or {},exclude_admin=False,exclude_transfers=False)
        f.pop('excluded_sources',None)
        wh,args=self.where(f)
        rows=self.query('''SELECT user_id, substr(utc,1,10) day,
              substr(utc,1,13) hour,CAST(substr(utc,15,2) AS INTEGER)/5 bucket
              FROM tx '''+wh+' ORDER BY user_id,utc',args)
        # Bucket times in UTC; concurrency-safe timezone-independent continuous streaks.
        activity=defaultdict(set)
        for r in rows:
            t=dt.datetime.fromisoformat(r['day']+'T'+r['hour'][-2:]+':00:00+00:00')
            block=int(t.timestamp()//300)+int(r['bucket'])
            activity[r['user_id']].add(block)
        flagged=[]
        for user,blocks in activity.items():
            best=run=0;last=None;end=None
            for b in sorted(blocks):
                run=run+1 if last is not None and b==last+1 else 1
                if run>best:best=run;end=b
                last=b
            flagged.append({'user_id':user,'active_blocks':len(blocks),'longest_blocks':best,
                'longest_hours':round(best/12,2),'flagged':best>=min_streak,
                'streak_start':dt.datetime.fromtimestamp((end-best+1)*300,dt.timezone.utc).isoformat() if end is not None else ''})
        return sorted(flagged,key=lambda x:x['longest_blocks'],reverse=True)

    def source_diagnostics(self, filters=None):
        rows=self.sources(filters)
        plus=[r for r in rows if r['net']>0 and r['name'] not in ('Unclassified','Admin adjustments')]
        minus=[r for r in rows if r['net']<0]
        tot=self.totals(filters)
        days=1
        if tot['first'] and tot['last']:
            first=dt.datetime.fromisoformat(tot['first'].replace('Z','+00:00'))
            last=dt.datetime.fromisoformat(tot['last'].replace('Z','+00:00'))
            days=max(1,(last-first).total_seconds()/86400)
        hints=[]
        if tot['net']>0:
            hints.append(('Net creation','Money is entering players’ balances faster than it is leaving. Consider stronger optional sinks rather than cutting every reward.'))
        elif tot['net']<0:
            hints.append(('Net contraction','Money is leaving players’ balances faster than it is entering. Check affordability of shops and accessibility for newer players.'))
        else:
            hints.append(('Balanced flows','Measured inflows and outflows roughly balance in this window. Check distribution before changing rates.'))
        if plus:
            r=max(plus,key=lambda a:a['net']); hints.append(('Largest net faucet: '+r['name'],f"Net +{r['net']:,} in this window. Check whether its rewards align with participation and effort."))
        if minus:
            r=min(minus,key=lambda a:a['net']); hints.append(('Largest net sink: '+r['name'],f"Net {r['net']:,} in this window. Inspect what players actually purchase or lose here."))
        users=self.users(filters)
        if len(users)>10:
            positive=sorted((max(0,u['net']) for u in users),reverse=True)
            total=sum(positive)
            if total:
                ten=max(1,math.ceil(len(positive)*.1))
                share=sum(positive[:ten])/total
                if share>=.5: hints.append(('Earnings concentration',f"Top 10% of users received {share:.0%} of positive net user gains. Investigate accessibility, rather than assuming everyone earns the average."))
        unclassified=next((r for r in self.sources(filters,by='domain') if r['name']=='Unclassified'),None)
        if unclassified and unclassified['events']:
            hints.append(('Unclassified audit events',f"{unclassified['events']:,} transactions do not match a known source pattern. They are kept separate so they do not distort known source totals."))
        return {'hints':hints,'days':days,'top_plus':plus[:5],'top_minus':minus[:5], 'net_30d':int(round(tot['net']*30/days))}

    def simulate(self, rules, filters=None, horizon=30, samples=1000, seed=67):
        """Counterfactual: observed frequencies unchanged; user-cluster bootstrap.

        rules: [{scope:'source'|'domain'|'item', key, payout, cost, volume}]
        Multipliers apply to recorded credits/debits, not individual game odds.
        """
        wh,args=self.where(filters)
        records=self.query('SELECT user_id,domain,source,item_id,amount FROM tx'+wh,args)
        if not records: raise ValueError('No transactions for this simulation window.')
        baseline=defaultdict(float); proposed=defaultdict(float)
        by_user_base=defaultdict(float);by_user_proposed=defaultdict(float)
        for r in records:
            value=r['amount']; expected=float(value)
            for rule in rules:
                name=rule['scope']; key=rule['key']
                if (name=='domain' and r['domain']==key) or (name=='source' and r['source']==key) or (name=='item' and r['item_id']==key):
                    # A cost multiplier scales negative amounts; a payout multiplier scales positive amounts.
                    expected *= (float(rule['payout']) if value>=0 else float(rule['cost']))*float(rule['volume'])
            baseline[r['source']]+=value;proposed[r['source']]+=expected
            by_user_base[r['user_id']]+=value;by_user_proposed[r['user_id']]+=expected
        totals=self.totals(filters)
        start=dt.datetime.fromisoformat(totals['first'].replace('Z','+00:00'))
        end=dt.datetime.fromisoformat(totals['last'].replace('Z','+00:00'))
        days=max((end-start).total_seconds()/86400,1.0)
        factor=horizon/days
        before=sum(baseline.values())*factor;after=sum(proposed.values())*factor
        # Random user resamples retain all of a person's events together.
        ci=None
        if len(by_user_base)>=3 and samples>0:
            import random
            rng=random.Random(seed)
            diffs=[(by_user_proposed[u]-by_user_base[u])*factor for u in by_user_base]
            n=len(diffs);sim=[]
            for _ in range(min(max(100,int(samples)),5000)):
                sim.append(sum(diffs[rng.randrange(n)] for _ in range(n)))
            sim.sort();ci=(sim[int(len(sim)*.025)],sim[min(len(sim)-1,int(len(sim)*.975))])
        return {'before':round(before),'after':round(after),'change':round(after-before),
            'ci':ci,'days':days,'horizon':horizon,'users':len(by_user_base),'events':len(records),
            'sources':[{'source':n,'before':round(baseline[n]*factor),'after':round(proposed[n]*factor),'change':round((proposed[n]-baseline[n])*factor)} for n in baseline]}

    def recommend_rebalance(self, filters=None, goal=0.0, max_adjustment=.20):
        """Bounded minimal-change rebalancing across configurable-looking faucets/sinks.

        Estimates use historical credit/debit sensitivity. These are candidates
        for review and are not recommendations to automatically deploy.
        """
        if not math.isfinite(goal) or not 0<=max_adjustment<=.5:
            raise ValueError('Goal must be finite and adjustment cap between 0 and 50%.')
        totals=self.totals(filters)
        if not totals['first'] or not totals['last']:
            raise ValueError('No historical transactions in selected period.')
        first=dt.datetime.fromisoformat(totals['first'].replace('Z','+00:00'))
        last=dt.datetime.fromisoformat(totals['last'].replace('Z','+00:00'))
        scale=30/max(1,(last-first).total_seconds()/86400)
        base=totals['net']*scale
        target_delta=goal-base
        names=[('Regular item shop','cost'),('Mafia profile shop','cost'),
               ('Role income','payout'),('Work','payout'),('Chat activity','payout'),
               ('Crime','payout'),('Slut','payout'),('Mafia quests','payout'),
               ('Mafia matches','payout')]
        by_name={r['name']:r for r in self.sources(filters)}
        candidates=[]
        for name,field in names:
            r=by_name.get(name)
            if not r:continue
            amount=(r['minted'] if field=='payout' else -r['burned'])*scale
            if abs(amount)>1:
                candidates.append((name,field,amount))
        if not candidates:
            raise ValueError('No configurable income/sink candidates in this period.')
        def get_changes(lam):
            return [max(-max_adjustment,min(max_adjustment,lam*sens)) for _,_,sens in candidates]
        def predicted(lam):
            return sum(sens*delta for (_,_,sens),delta in zip(candidates,get_changes(lam)))
        max_possible=sum(abs(sens)*max_adjustment for _,_,sens in candidates)
        desired=max(-max_possible,min(max_possible,target_delta))
        left=-1.;right=1.
        # Positive lambda makes a positive net delta; negative reverses it.
        for _ in range(100):
            mid=(left+right)/2
            if predicted(mid)<desired:left=mid
            else:right=mid
        changes=get_changes((left+right)/2)
        rules=[]
        for (name,field,sens),delta in zip(candidates,changes):
            if abs(delta)<.0005:continue
            rule={'scope':'source','key':name,'payout':1.0,'cost':1.0,'volume':1.0}
            rule[field]=round(1.0+delta,6)
            rules.append(rule)
        outcome=base+sum(sens*delta for (_,_,sens),delta in zip(candidates,changes))
        return {'rules':rules,'baseline':round(base),'goal':round(goal),'estimate':round(outcome),
                'remainder':round(goal-outcome),'cap':max_adjustment}

    def export_csv(self,path,rows):
        if not rows: raise ValueError('Nothing to export.')
        with open(path,'w',encoding='utf-8-sig',newline='') as fh:
            writer=csv.DictWriter(fh,fieldnames=list(rows[0].keys()),extrasaction='ignore')
            writer.writeheader();writer.writerows(rows)
