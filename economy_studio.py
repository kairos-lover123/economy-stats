"""Economy Studio 2.0.5. Run this file directly from Visual Studio.

Standard-library application. User databases are selected locally and are not
bundled with the application or modified by the analytics importer.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import queue
import os
import re
import sys
import threading
import tkinter as tk
from collections import defaultdict
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from economy_core import EconomyStore, APP_DIR, GAME_NAMES, utc_display

HERE=Path(__file__).resolve().parent
FONT='Segoe UI'
COLORS={
 'dark':{'bg':'#10141C','side':'#151B26','panel':'#192232','panel2':'#202B3C','border':'#2C3A4C',
   'text':'#EDF3FC','muted':'#9EAFBF','accent':'#76B9F0','accent2':'#A58DF2','green':'#6DD5A1',
   'red':'#F58C99','amber':'#F5C878','table':'#182231','hover':'#2A384B'},
 'light':{'bg':'#F1F5F9','side':'#FFFFFF','panel':'#FFFFFF','panel2':'#E8EFF6','border':'#D9E3EE',
   'text':'#1D2939','muted':'#66788D','accent':'#236BA6','accent2':'#7046B8','green':'#13865E',
   'red':'#BB3E55','amber':'#A66C16','table':'#FFFFFF','hover':'#E0EAF4'}
}


def money(x,sign=False):
    try:
        v=float(x)
        if abs(v)<.005: v=0
        return f'{v:+,.0f}' if sign else f'{v:,.0f}'
    except (ValueError,TypeError): return str(x)


def short(x):
    try:
        x=float(x)
        ab=abs(x)
        return f'{x/1e9:.2f}B' if ab>=1e9 else f'{x/1e6:.2f}M' if ab>=1e6 else f'{x/1e3:.1f}K' if ab>=1e3 else f'{x:,.0f}'
    except (TypeError,ValueError): return str(x)


def local_to_utc(date_str,end=False):
    date_str=date_str.strip()
    if not date_str: return ''
    try:
        obj=dt.datetime.strptime(date_str,'%Y-%m-%d')
    except ValueError as e:
        raise ValueError('Use YYYY-MM-DD dates, such as 2026-10-15.') from e
    if end:obj=obj.replace(hour=23,minute=59,second=59,microsecond=999999)
    return obj.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


class HoverTip:
    def __init__(self,widget,message):
        self.widget=widget;self.message=message;self.popup=None
        widget.bind('<Enter>',self.enter,add='+')
        widget.bind('<Leave>',self.leave,add='+')
        widget.bind('<ButtonPress>',self.leave,add='+')
    def enter(self,event=None):
        if self.popup:return
        try:
            x=self.widget.winfo_rootx()+20;y=self.widget.winfo_rooty()+self.widget.winfo_height()+8
            top=tk.Toplevel(self.widget);top.overrideredirect(True);top.wm_geometry(f'+{x}+{y}')
            lbl=tk.Label(top,text=self.message,bg='#253248',fg='#EAF1F9',font=(FONT,10),
               justify='left',wraplength=350,padx=12,pady=9)
            lbl.pack();self.popup=top
        except tk.TclError:pass
    def leave(self,event=None):
        if self.popup:
            try:self.popup.destroy()
            except tk.TclError:pass
            self.popup=None


class ScrollPage(tk.Frame):
    def __init__(self,parent,c):
        super().__init__(parent,bg=c['bg'])
        self.c=c
        self.canvas=tk.Canvas(self,bg=c['bg'],highlightthickness=0,bd=0)
        self.scroll=ttk.Scrollbar(self,orient='vertical',command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side='left',fill='both',expand=True)
        self.scroll.pack(side='right',fill='y')
        self.content=tk.Frame(self.canvas,bg=c['bg'])
        self.window=self.canvas.create_window((0,0),window=self.content,anchor='nw')
        self.content.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>',lambda e:self.canvas.itemconfigure(self.window,width=e.width))
        self.canvas.bind('<Enter>',lambda e:self._wheel_bind(True))
        self.canvas.bind('<Leave>',lambda e:self._wheel_bind(False))
        self.bind('<Destroy>',lambda e:self._wheel_bind(False))
    def _wheel_bind(self,active):
        if active:self.canvas.bind_all('<MouseWheel>',self._onwheel)
        else:self.canvas.unbind_all('<MouseWheel>')
    def _onwheel(self,e):
        try:self.canvas.yview_scroll(int(-e.delta/120),'units')
        except tk.TclError:pass


class DataGrid(tk.Frame):
    """Resortable, searchable Treeview with pagination and CSV/clipboard export."""
    def __init__(self,parent,c,columns,rows=None,labels=None,height=13,on_open=None,click_name=None,
                 search=True,export=None):
        super().__init__(parent,bg=c['panel'])
        self.c=c;self.columns=list(columns);self.labels=labels or {};self.rows=[];self.filtered=[]
        self.on_open=on_open;self.export=export;self.page=0;self.size=75;self.order_col=None;self.reverse=True
        self.search_var=tk.StringVar()
        top=tk.Frame(self,bg=c['panel']);top.pack(fill='x',padx=14,pady=(12,7))
        tk.Label(top,text=click_name or 'Records',bg=c['panel'],fg=c['text'],font=(FONT,11,'bold')).pack(side='left')
        if self.on_open:
            tk.Button(top,text='View details',command=self.open_row,**flat_button(c,True)).pack(side='right',padx=(6,0))
        tk.Button(top,text='Export CSV',command=self.export_csv,**flat_button(c)).pack(side='right',padx=(6,0))
        tk.Button(top,text='Copy rows',command=self.copy_rows,**flat_button(c)).pack(side='right',padx=(6,0))
        if search:
            entry=tk.Entry(top,textvariable=self.search_var,bg=c['panel2'],fg=c['text'],
                 insertbackground=c['text'],relief='flat',width=24,font=(FONT,10))
            entry.pack(side='right',ipady=6,padx=6)
            self.search_var.trace_add('write',lambda *_:self.apply_search())
            HoverTip(entry,'Searches the currently loaded table across every column.')
        body=tk.Frame(self,bg=c['panel']);body.pack(fill='both',expand=True,padx=12)
        self.tree=ttk.Treeview(body,columns=self.columns,show='headings',height=height,selectmode='browse')
        self.v=ttk.Scrollbar(body,orient='vertical',command=self.tree.yview)
        self.h=ttk.Scrollbar(self,orient='horizontal',command=self.tree.xview)
        self.tree.configure(yscrollcommand=self.v.set,xscrollcommand=self.h.set)
        self.tree.pack(side='left',fill='both',expand=True);self.v.pack(side='right',fill='y')
        self.h.pack(fill='x',padx=12,pady=(0,5))
        for col in self.columns:
            self.tree.heading(col,text=self.labels.get(col,col.replace('_',' ').title()),command=lambda n=col:self.sort(n))
            width=135
            if col in ('name','reason','item_name','source','detail','item_id'):width=250
            if col in ('utc','first','last','last_purchase','last_transaction'):width=175
            if col in ('user_id','item_group'):width=185
            self.tree.column(col,width=width,minwidth=70,anchor='e' if col in ('net','minted','burned','events','users','buyers','purchases','gross_spend','net_spend','avg_spend','change','active_days','longest_hours','active_5m','amount','cash','bank','spent','buy_rate','bets','stakes','payouts','extra_costs','return_pct','net_per_bet','winning_events') else 'w',stretch=True)
        self.tree.bind('<Double-1>',lambda e:self.open_row())
        self.tree.bind('<Return>',lambda e:self.open_row())
        self.tree.bind('<Control-c>',lambda e:self.copy_rows())
        bottom=tk.Frame(self,bg=c['panel']);bottom.pack(fill='x',padx=12,pady=(3,13))
        self.info=tk.Label(bottom,text='',bg=c['panel'],fg=c['muted'],font=(FONT,9));self.info.pack(side='left')
        tk.Button(bottom,text='Next',command=lambda:self.goto(self.page+1),**flat_button(c)).pack(side='right')
        tk.Button(bottom,text='Previous',command=lambda:self.goto(self.page-1),**flat_button(c)).pack(side='right',padx=(0,7))
        self.set_rows(rows or [])

    def set_rows(self,rows):
        self.rows=list(rows);self.apply_search()
    def apply_search(self):
        term=self.search_var.get().casefold().strip()
        self.filtered=[r for r in self.rows if not term or any(term in str(v).casefold() for v in r.values())]
        if self.order_col:self.sort(self.order_col,refresh=False)
        self.page=0;self.refresh()
    def sort(self,column,refresh=True):
        if not refresh:reverse=self.reverse
        else:
            self.reverse=not self.reverse if self.order_col==column else True
            self.order_col=column;reverse=self.reverse
        self.filtered.sort(key=lambda r:(r.get(column) is None, r.get(column) if isinstance(r.get(column),(int,float)) else str(r.get(column,'')).casefold()),reverse=reverse)
        if refresh:self.page=0;self.refresh()
    def goto(self,index):
        maxpage=max(0,(len(self.filtered)-1)//self.size)
        self.page=max(0,min(maxpage,index));self.refresh()
    def refresh(self):
        existing=self.tree.get_children()
        if existing:self.tree.delete(*existing)
        start=self.page*self.size
        for n,r in enumerate(self.filtered[start:start+self.size]):
            vals=[]
            for col in self.columns:
                val=r.get(col,'')
                if col in ('utc','first','last','last_purchase','last_transaction','streak_start') and isinstance(val,str) and 'T' in val:
                    val=utc_display(val)
                elif isinstance(val,float):val=f'{val:,.2f}'
                elif isinstance(val,int):val=f'{val:,}'
                vals.append(val)
            self.tree.insert('', 'end',iid=str(n),values=vals,tags=('even' if n%2==0 else 'odd',))
        self.tree.tag_configure('even',background=self.c['table'],foreground=self.c['text'])
        self.tree.tag_configure('odd',background=self.c['panel'],foreground=self.c['text'])
        end=min(start+self.size,len(self.filtered))
        self.info.config(text=f'{start+1 if end else 0:,} to {end:,} of {len(self.filtered):,} rows. Double-click to inspect.')
    def selected_row(self):
        sel=self.tree.selection()
        if not sel:return None
        index=self.page*self.size+int(sel[0])
        return self.filtered[index] if index<len(self.filtered) else None
    def open_row(self):
        row=self.selected_row()
        if row and self.on_open:self.on_open(row)
    def copy_rows(self):
        sel=self.selected_row()
        if sel:lines=[sel]
        else:lines=self.filtered[self.page*self.size:self.page*self.size+self.size]
        data='\t'.join(self.columns)+'\n'+'\n'.join('\t'.join(str(r.get(k,'')) for k in self.columns) for r in lines)
        self.clipboard_clear();self.clipboard_append(data)
    def export_csv(self):
        path=filedialog.asksaveasfilename(parent=self,defaultextension='.csv',filetypes=[('CSV file','*.csv')])
        if not path:return
        try:
            import csv
            with open(path,'w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=self.columns,extrasaction='ignore')
                w.writeheader();w.writerows(self.filtered)
        except Exception as e:messagebox.showerror('Export failed',str(e),parent=self)


class FlowChart(tk.Canvas):
    def __init__(self,parent,c,mode='bars',height=245):
        super().__init__(parent,height=height,bg=c['panel'],bd=0,highlightthickness=0)
        self.c=c;self.points=[];self.mode=mode
        self.bind('<Configure>',lambda e:self.draw())
    def configure_data(self,points,mode=None):
        self.points=points[:35]
        if mode:self.mode=mode
        self.draw()
    def draw(self):
        self.delete('all');w=self.winfo_width();h=self.winfo_height()
        if w<100 or not self.points:return
        l=56;r=w-26;t=25;b=h-40
        self.create_line(l,b,r,b,fill=self.c['border'],width=1)
        values=[float(p[1]) for p in self.points]
        minimum=min(0,min(values));maximum=max(0,max(values))
        if maximum==minimum:maximum+=1
        span=maximum-minimum
        def yp(x):return b-(x-minimum)/span*(b-t)
        zero=yp(0)
        self.create_line(l,zero,r,zero,fill=self.c['border'],dash=(4,4))
        for frac in (0,.5,1):
            val=minimum+(maximum-minimum)*frac
            y=yp(val)
            self.create_text(l-7,y,text=short(val),fill=self.c['muted'],font=(FONT,9),anchor='e')
        if self.mode=='line' and len(values)>1:
            pts=[]
            for i,val in enumerate(values):
                x=l+(r-l)*i/(len(values)-1)
                pts.extend([x,yp(val)])
            self.create_line(*pts,fill=self.c['accent'],width=3,smooth=False)
            for i,val in enumerate(values):
                x=l+(r-l)*i/(len(values)-1);y=yp(val)
                self.create_oval(x-3,y-3,x+3,y+3,fill=self.c['accent'],outline=self.c['panel'])
        else:
            slot=(r-l)/len(values)
            for i,val in enumerate(values):
                x=l+slot*i+slot*.16;end=x+slot*.68;y=yp(val)
                self.create_rectangle(x,min(y,zero),end,max(y,zero)+.7,
                    fill=self.c['green'] if val>=0 else self.c['red'],outline='')
        labels=[0,len(values)//2,len(values)-1] if self.mode=='line' else [int(i*max(1,len(values)//5)) for i in range(6)]
        for i in sorted(set(max(0,min(len(values)-1,v)) for v in labels)):
            x=l+(r-l)*i/max(1,len(values)-1) if self.mode=='line' else l+(r-l)*(i+.5)/len(values)
            label=str(self.points[i][0])
            if len(label)>17:label=label[:16]+'..'
            self.create_text(x,h-16,text=label,fill=self.c['muted'],font=(FONT,9))


def flat_button(c,accent=False):
    return dict(bg=c['accent'] if accent else c['panel2'],fg=c['side'] if accent else c['text'],
                activebackground=c['hover'],activeforeground=c['text'],relief='flat',bd=0,
                font=(FONT,10,'bold'),cursor='hand2',padx=13,pady=7,highlightthickness=0)


class EconomyStudio(tk.Tk):
    NAV=[('dashboard','Overview'),('sources','All income sources'),('games','Games'),('flows','Flow summary'),('shops','Shop intelligence'),
         ('users','Members'),('trends','Trends'),('activity','Activity and macro'),
         ('scenario','Scenario lab')]
    def __init__(self):
        super().__init__()
        self.title('Economy Studio | The Spike: Cross')
        if sys.platform=='win32' and (HERE/'icon.ico').exists():
            try:self.iconbitmap(str(HERE/'icon.ico'))
            except tk.TclError:pass
        self.geometry('1480x920');self.minsize(1080,700)
        self.settings_path=APP_DIR/'preferences.json'
        try:self.settings=json.loads(self.settings_path.read_text())
        except (OSError,ValueError):self.settings={}
        self.theme=self.settings.get('theme','dark');self.c=COLORS.get(self.theme,COLORS['dark'])
        self.store=EconomyStore();self.messages=queue.Queue();self.loading=False
        self.current='dashboard';self.page=None;self.nav_buttons={}
        self.filters={'exclude_transfers':True,'exclude_admin':True}
        self.excluded_sources=set()
        self.quick=tk.StringVar(value='All history')
        self.start_var=tk.StringVar(value='');self.end_var=tk.StringVar(value='')
        self.transfers_var=tk.BooleanVar(value=False)
        self.adjustments_var=tk.BooleanVar(value=False)
        self.shop_view=tk.StringVar(value='Mafia shop');self.shop_group=tk.StringVar(value='All categories')
        self.source_domain=tk.StringVar(value='All categories');self.source_sign=tk.StringVar(value='All flows')
        self.shop_search=tk.StringVar()
        self.selected_source=None;self.source_return='sources';self.selected_item=None;self.selected_user=None
        self.selected_scope=tk.StringVar(value='Source');self.selected_target=tk.StringVar()
        self.rules=[];self.last_sim=None;self.scenario_item_keys={}
        self.chart_unit=tk.StringVar(value='Daily')
        self.status=tk.StringVar(value='Choose a database to start.')
        self.configure(bg=self.c['bg']);self.style_widgets();self.build_shell()
        self.after(80,self.poll)
        self.after(250,self.autoload)
        self.protocol('WM_DELETE_WINDOW',self.exit_app)

    def exit_app(self):
        APP_DIR.mkdir(exist_ok=True,parents=True)
        self.settings_path.write_text(json.dumps({'theme':self.theme},indent=2))
        self.destroy()

    def style_widgets(self):
        c=self.c;st=ttk.Style(self)
        st.theme_use('clam')
        st.configure('Treeview',background=c['table'],fieldbackground=c['table'],foreground=c['text'],
             borderwidth=0,rowheight=30,font=(FONT,10))
        st.map('Treeview',background=[('selected',c['accent2'])],foreground=[('selected','#FFFFFF')])
        st.configure('Treeview.Heading',background=c['panel2'],foreground=c['text'],relief='flat',font=(FONT,10,'bold'),padding=(8,10))
        st.map('Treeview.Heading',background=[('active',c['hover'])])
        st.configure('TScrollbar',troughcolor=c['panel'],background=c['panel2'],arrowcolor=c['text'])
        st.configure('TCombobox',fieldbackground=c['panel2'],background=c['panel2'],foreground=c['text'],
                    arrowcolor=c['text'],font=(FONT,10),padding=5)
        st.map('TCombobox',fieldbackground=[('readonly',c['panel2'])],foreground=[('readonly',c['text'])])
        st.configure('TCheckbutton',background=c['bg'],foreground=c['text'],font=(FONT,10))
        st.map('TCheckbutton',background=[('active',c['bg'])])

    def build_shell(self):
        c=self.c
        self.shell=tk.Frame(self,bg=c['bg']);self.shell.pack(fill='both',expand=True)
        side=tk.Frame(self.shell,bg=c['side'],width=224);side.pack(side='left',fill='y');side.pack_propagate(False)
        topbrand=tk.Frame(side,bg=c['side']);topbrand.pack(fill='x',padx=20,pady=(29,27))
        tk.Label(topbrand,text='ECONOMY',bg=c['side'],fg=c['accent'],font=(FONT,17,'bold')).pack(anchor='w')
        tk.Label(topbrand,text='S T U D I O    /    2.0.5',bg=c['side'],fg=c['muted'],font=(FONT,9,'bold')).pack(anchor='w',pady=(1,0))
        tk.Label(side,text='WORKSPACE',bg=c['side'],fg=c['muted'],font=(FONT,9,'bold')).pack(anchor='w',padx=21,pady=(6,9))
        for key,label in self.NAV:
            wrap=tk.Frame(side,bg=c['side']);wrap.pack(fill='x',padx=(10,9),pady=2)
            b=tk.Button(wrap,text='   '+label,command=lambda k=key:self.navigate(k),
                        bg=c['side'],fg=c['muted'],activebackground=c['hover'],activeforeground=c['text'],
                        font=(FONT,10),anchor='w',relief='flat',bd=0,highlightthickness=0,pady=9,cursor='hand2')
            b.pack(fill='x');self.nav_buttons[key]=b
        bottom=tk.Frame(side,bg=c['side']);bottom.pack(side='bottom',fill='x',padx=18,pady=20)
        tk.Button(bottom,text='Switch theme',command=self.switch_theme,**flat_button(c)).pack(fill='x')
        tk.Label(bottom,text='Local analysis. Original database stays untouched.',bg=c['side'],fg=c['muted'],font=(FONT,8)).pack(pady=(13,0))
        right=tk.Frame(self.shell,bg=c['bg']);right.pack(side='left',fill='both',expand=True)
        toolbar=tk.Frame(right,bg=c['side'],height=77);toolbar.pack(fill='x');toolbar.pack_propagate(False)
        form=tk.Frame(toolbar,bg=c['side']);form.pack(side='left',fill='y',padx=24)
        tk.Label(form,text='Period',bg=c['side'],fg=c['muted'],font=(FONT,9)).pack(side='left')
        self.range_combo=ttk.Combobox(form,textvariable=self.quick,values=['All history','Last 7 days','Last 30 days','Last 90 days','Custom'],state='readonly',width=15)
        self.range_combo.pack(side='left',padx=(8,12));self.range_combo.bind('<<ComboboxSelected>>',lambda e:self.apply_period())
        self.start_entry=self.small_entry(form,self.start_var,12);self.start_entry.pack(side='left',padx=(0,6))
        self.start_entry.bind('<KeyRelease>',lambda e:self.quick.set('Custom'))
        tk.Label(form,text='to',bg=c['side'],fg=c['muted']).pack(side='left')
        self.end_entry=self.small_entry(form,self.end_var,12);self.end_entry.pack(side='left',padx=(6,8))
        self.end_entry.bind('<KeyRelease>',lambda e:self.quick.set('Custom'))
        tk.Button(form,text='Apply',command=self.apply_period,**flat_button(c)).pack(side='left')
        actions=tk.Frame(toolbar,bg=c['side']);actions.pack(side='right',padx=23)
        tk.Button(actions,text='Open database',command=self.choose_file,**flat_button(c,True)).pack(side='right')
        self.main_area=tk.Frame(right,bg=c['bg']);self.main_area.pack(fill='both',expand=True)
        statusbar=tk.Frame(right,bg=c['side'],height=30);statusbar.pack(fill='x',side='bottom')
        self.status_label=tk.Label(statusbar,textvariable=self.status,bg=c['side'],fg=c['muted'],font=(FONT,9),anchor='w')
        self.status_label.pack(fill='both',padx=18)
        self.navigate(self.current)

    def small_entry(self,parent,var,width=16):
        c=self.c
        return tk.Entry(parent,textvariable=var,bg=c['panel2'],fg=c['text'],relief='flat',bd=0,
                 insertbackground=c['text'],font=(FONT,10),width=width,highlightthickness=1,
                 highlightcolor=c['accent'],highlightbackground=c['border'])

    def switch_theme(self):
        self.theme='light' if self.theme=='dark' else 'dark'
        self.c=COLORS[self.theme]
        self.style_widgets();self.shell.destroy();self.build_shell()

    def autoload(self):
        paths=[]
        for root in (HERE,HERE.parent):
            for name in ('economy-stats.dht',):
                p=root/name
                if p.exists():paths=[p];break
            if paths:break
        if not paths:
            for root in (HERE,HERE.parent):
                parts=sorted(root.glob('*.part[0-9][0-9][0-9]'))
                if parts:paths=parts;break
        if paths:self.load_paths(paths)

    def choose_file(self):
        paths=filedialog.askopenfilenames(title='Open DHT or all fragment files',parent=self,
                    filetypes=[('DHT and split databases','*.dht *.sqlite *.db *.part*'),('All files','*.*')])
        if paths:
            paths=list(map(Path,paths))
            if len(paths)==1 and re.search(r'\.part\d+$',str(paths[0]),re.I):
                m=re.match(r'^(.*)\.part\d+$',str(paths[0]),re.I)
                if m:
                    siblings=sorted(paths[0].parent.glob(Path(m.group(1)).name+'.part*'))
                    if len(siblings)>1:paths=siblings
            self.load_paths(paths)

    def load_paths(self,paths):
        if self.loading:return
        self.loading=True
        self.status.set('Reading audit history...')
        self.show_loading()
        def task():
            try:
                st=EconomyStore()
                result=st.load(paths,progress=lambda msg:self.messages.put(('status',msg)))
                self.messages.put(('loaded',(st,result)))
            except Exception as e:self.messages.put(('error',str(e)))
        threading.Thread(target=task,daemon=True).start()

    def show_loading(self):
        for w in self.main_area.winfo_children():w.destroy()
        p=tk.Frame(self.main_area,bg=self.c['bg']);p.pack(expand=True)
        tk.Label(p,text='Preparing the economy workspace',bg=self.c['bg'],fg=self.c['text'],font=(FONT,19,'bold')).pack()
        tk.Label(p,text='Identifying income sources, purchases and account activity.',bg=self.c['bg'],fg=self.c['muted'],font=(FONT,11)).pack(pady=8)

    def poll(self):
        try:
            for _ in range(15):
                kind,payload=self.messages.get_nowait()
                if kind=='status':self.status.set(payload)
                elif kind=='error':
                    self.loading=False;self.status.set('Import error: '+payload)
                    messagebox.showerror('Could not open database',payload,parent=self)
                    self.navigate('dashboard')
                elif kind=='loaded':
                    self.store,_=payload;self.loading=False
                    self.status.set(f"{self.store.stats.get('events',0):,} records | {self.store.stats.get('users',0):,} users | {self.store.note}")
                    self.apply_period()
                elif kind=='macro':
                    self.status.set('Activity analysis finished')
                    self.macro_rows=payload
                    if self.current=='activity':self.navigate('activity')
                elif kind=='macro_error':
                    self.status.set('Activity analysis failed: '+payload)
        except queue.Empty:pass
        try:self.after(80,self.poll)
        except tk.TclError:pass

    def ready(self):return self.store.snapshot is not None
    def apply_period(self):
        if not self.ready():return
        end=self.store.stats.get('last')
        if not end:return
        name=self.quick.get()
        if name!='Custom':
            self.start_var.set('');self.end_var.set('')
        f={'exclude_admin':not self.adjustments_var.get(),'exclude_transfers':not self.transfers_var.get(),
           'excluded_sources':set(self.excluded_sources)}
        try:
            if name=='Custom':
                if self.start_var.get():f['start']=local_to_utc(self.start_var.get())
                if self.end_var.get():f['end']=local_to_utc(self.end_var.get(),True)
            elif name!='All history':
                days={'Last 7 days':7,'Last 30 days':30,'Last 90 days':90}.get(name)
                if days:
                    last=dt.datetime.fromisoformat(end.replace('Z','+00:00'))
                    f['start']=(last-dt.timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        except ValueError as e:
            messagebox.showwarning('Date format',str(e),parent=self);return
        if f.get('start') and f.get('end') and f['start']>f['end']:
            messagebox.showwarning('Invalid period','Start date must be before end date.',parent=self);return
        self.filters=f;self.navigate(self.current)

    def filter_panel(self,parent):
        c=self.c
        box=tk.Frame(parent,bg=c['panel']);box.pack(fill='x',pady=(0,15))
        tk.Label(box,text='WHAT TO INCLUDE',font=(FONT,9,'bold'),bg=c['panel'],fg=c['muted']).pack(side='left',padx=14,pady=11)
        for label,var in [('Player transfers',self.transfers_var),('Admin adjustments',self.adjustments_var)]:
            cb=tk.Checkbutton(box,text=label,variable=var,command=self.apply_period,
                bg=c['panel'],fg=c['text'],selectcolor=c['panel2'],activebackground=c['panel'],activeforeground=c['text'],
                font=(FONT,9),relief='flat',bd=0)
            cb.pack(side='left',padx=(8,12))
        tk.Button(box,text=f'Exclude sources ({len(self.excluded_sources)})',command=self.edit_exclusions,
                **flat_button(c)).pack(side='right',padx=14)

    def edit_exclusions(self):
        if not self.ready():return
        c=self.c;top=tk.Toplevel(self);top.title('Exclude sources');top.geometry('450x585')
        top.configure(bg=c['panel']);top.transient(self);top.grab_set()
        tk.Label(top,text='Choose sources to exclude',bg=c['panel'],fg=c['text'],
            font=(FONT,15,'bold')).pack(anchor='w',padx=18,pady=(18,5))
        tk.Label(top,text='Excluded sources affect every view and scenario in this period.',
            bg=c['panel'],fg=c['muted'],wraplength=405).pack(anchor='w',padx=18,pady=(0,11))
        box=tk.Listbox(top,bg=c['panel2'],fg=c['text'],selectbackground=c['accent2'],
             selectforeground='#FFFFFF',selectmode='multiple',font=(FONT,10),bd=0,relief='flat',
             highlightbackground=c['border'],highlightthickness=1,exportselection=False)
        box.pack(fill='both',expand=True,padx=18)
        names=sorted(r['name'] for r in self.store.sources({'exclude_admin':False,'exclude_transfers':False}))
        for i,name in enumerate(names):
            box.insert('end',name)
            if name in self.excluded_sources:box.selection_set(i)
        def apply():
            self.excluded_sources={names[i] for i in box.curselection()}
            top.destroy();self.apply_period()
        controls=tk.Frame(top,bg=c['panel']);controls.pack(fill='x',padx=18,pady=15)
        tk.Button(controls,text='Clear all',command=lambda:box.selection_clear(0,'end'),**flat_button(c)).pack(side='left')
        tk.Button(controls,text='Apply exclusions',command=apply,**flat_button(c,True)).pack(side='right')

    def navigate(self,key):
        self.current=key
        for k,b in self.nav_buttons.items():
            b.configure(bg=self.c['panel2'] if k==key else self.c['side'],fg=self.c['text'] if k==key else self.c['muted'])
        for w in self.main_area.winfo_children():w.destroy()
        self.page=ScrollPage(self.main_area,self.c);self.page.pack(fill='both',expand=True)
        if not self.ready():
            self.empty_state(self.page.content)
            return
        funcs={'dashboard':self.page_dashboard,'sources':self.page_sources,'games':self.page_games,'flows':self.page_flows,'shops':self.page_shops,
            'users':self.page_users,'trends':self.page_trends,'activity':self.page_activity,
            'scenario':self.page_scenario,
            'source_detail':self.page_source_detail,
            'item_detail':self.page_item_detail,'user_detail':self.page_user_detail}
        try:funcs.get(key,self.page_dashboard)(self.page.content)
        except Exception as e:
            self.status.set(f'Unable to render view: {e}')
            self.title_line(self.page.content,'Page error','The data is safe. Choose another view.')
            tk.Label(self.page.content,text=str(e),bg=self.c['bg'],fg=self.c['red'],font=(FONT,11),wraplength=700).pack(anchor='w',pady=12)

    def empty_state(self,parent):
        self.title_line(parent,'Bring your economy into focus','Choose a .dht SQLite file or select all available .part### fragments.')
        c=self.c;card=self.panel(parent)
        tk.Label(card,text='Start with your Discord History Tracker database',font=(FONT,16,'bold'),bg=c['panel'],fg=c['text']).pack(anchor='w',padx=22,pady=(24,6))
        tk.Label(card,text='Automatic source grouping, purchase-level shop analytics, activity insights and scenario testing.',
                 bg=c['panel'],fg=c['muted'],wraplength=760,justify='left',font=(FONT,11)).pack(anchor='w',padx=22,pady=(0,17))
        tk.Button(card,text='Choose database files',command=self.choose_file,**flat_button(c,True)).pack(anchor='w',padx=22,pady=(0,24))

    def title_line(self,parent,name,subtitle='',back=None):
        c=self.c;wrap=tk.Frame(parent,bg=c['bg']);wrap.pack(fill='x',padx=25,pady=(26,16))
        if back:tk.Button(wrap,text='<  '+back[0],command=lambda:self.navigate(back[1]),**flat_button(c)).pack(anchor='w',pady=(0,10))
        tk.Label(wrap,text=name,bg=c['bg'],fg=c['text'],font=(FONT,23,'bold')).pack(anchor='w')
        if subtitle:tk.Label(wrap,text=subtitle,bg=c['bg'],fg=c['muted'],font=(FONT,10),wraplength=980,justify='left').pack(anchor='w',pady=(4,0))

    def panel(self,parent,pad=0):
        c=self.c;frame=tk.Frame(parent,bg=c['panel'],highlightbackground=c['border'],highlightthickness=1)
        frame.pack(fill='x',padx=25,pady=(0,17),ipady=pad)
        return frame

    def section(self,parent,title,detail=None):
        c=self.c;row=tk.Frame(parent,bg=c['bg']);row.pack(fill='x',padx=27,pady=(5,10))
        tk.Label(row,text=title,bg=c['bg'],fg=c['text'],font=(FONT,14,'bold')).pack(side='left')
        if detail:tk.Label(row,text=detail,bg=c['bg'],fg=c['muted'],font=(FONT,9)).pack(side='right')

    def stats_cards(self,parent,items):
        c=self.c;wrap=tk.Frame(parent,bg=c['bg']);wrap.pack(fill='x',padx=25,pady=(0,16))
        for i,(label,value,expl,shade) in enumerate(items):
            pane=tk.Frame(wrap,bg=c['panel'],highlightbackground=c['border'],highlightthickness=1)
            pane.grid(row=0,column=i,sticky='nsew',padx=(0,12) if i<len(items)-1 else 0)
            wrap.grid_columnconfigure(i,weight=1)
            tk.Label(pane,text=label.upper(),bg=c['panel'],fg=c['muted'],font=(FONT,9,'bold')).pack(anchor='w',padx=15,pady=(15,5))
            tk.Label(pane,text=str(value),bg=c['panel'],fg=c.get(shade,c['text']),font=(FONT,20,'bold')).pack(anchor='w',padx=15)
            tk.Label(pane,text=expl,bg=c['panel'],fg=c['muted'],font=(FONT,9),wraplength=245,justify='left').pack(anchor='w',padx=15,pady=(6,15))
            HoverTip(pane,expl)

    def text_panel(self,parent,title,lines):
        c=self.c;p=self.panel(parent)
        tk.Label(p,text=title,bg=c['panel'],fg=c['text'],font=(FONT,12,'bold')).pack(anchor='w',padx=17,pady=(15,8))
        for heading,detail in lines:
            line=tk.Frame(p,bg=c['panel']);line.pack(fill='x',padx=17,pady=(0,11))
            tk.Label(line,text=heading,bg=c['panel'],fg=c['accent'],font=(FONT,10,'bold')).pack(anchor='w')
            tk.Label(line,text=detail,bg=c['panel'],fg=c['muted'],font=(FONT,10),wraplength=820,justify='left').pack(anchor='w',pady=(3,0))

    def grid(self,parent,rows,cols,title,opener=None,labels=None,height=11):
        p=self.panel(parent);table=DataGrid(p,self.c,cols,rows,labels,height=height,on_open=opener,click_name=title)
        table.pack(fill='x');return table

    def _source_open(self,r):
        self.source_return = self.current if self.current in ('games','sources','flows') else 'sources'
        label = r.get('name') or r.get('source')
        self.selected_source = ('identified',r['domain'],label) if r.get('domain') else label
        self.navigate('source_detail')
    def _item_open(self,r):
        self.selected_item=(r['source'],r['item_id'],r.get('item_name',r.get('name','')))
        self.navigate('item_detail')
    def _user_open(self,r):
        self.selected_user=r['user_id'];self.navigate('user_detail')

    def page_dashboard(self,p):
        self.title_line(p,'Economy overview','Economy health at a glance. Net is always actual balance movement, not gross winnings.')
        self.filter_panel(p)
        actions=tk.Frame(p,bg=self.c['bg']);actions.pack(fill='x',padx=25,pady=(0,15))
        tk.Button(actions,text='Browse every income source',command=lambda:self.navigate('sources'),
                  **flat_button(self.c,True)).pack(side='left',padx=(0,9))
        tk.Button(actions,text='View individual games',command=lambda:self.navigate('games'),
                  **flat_button(self.c)).pack(side='left')
        t=self.store.totals(self.filters);diag=self.store.source_diagnostics(self.filters)
        r=t['burned']/t['minted']*100 if t['minted'] else 0
        self.stats_cards(p,[('Net supply change',money(t['net'],True),'Credits less debits in selected period.','green' if t['net']>=0 else 'red'),
             ('Gross created',short(t['minted']),'Positive user balance movements.','text'),
             ('Gross removed',short(t['burned']),'Negative user balance movements.','text'),
             ('Economy users',money(t['users']),'Unique accounts with audit activity.','accent')])
        self.stats_cards(p,[('Recorded changes',money(t['events']),'Valid balance changes.','text'),
             ('Removal rate',f'{r:.1f}%','Removed per 100 currency added.','amber'),
             ('30-day projection',money(diag['net_30d'],True),'Linear projection, not a forecast.','text'),
             ('Observed window',f"{diag['days']:.1f} days",'Based on first and last included records.','text')])
        self.section(p,'Money flow by source','Click a row below for details')
        sources=self.store.sources(self.filters)
        chart=self.panel(p);plot=FlowChart(chart,self.c,height=230)
        plot.pack(fill='x',padx=17,pady=12)
        chart_rows=sorted(sources,key=lambda r:abs(r['net']),reverse=True)[:12]
        plot.configure_data([(r['name'],r['net']) for r in chart_rows])
        self.grid(p,sources[:18],['name','net','minted','burned','users','events'],'Largest money sources and sinks',self._source_open,height=12)
        self.section(p,'Decision support')
        self.text_panel(p,'Potential adjustments to investigate',diag['hints'])
        if 'PARTIAL' in self.store.note:
            self.text_panel(p,'Coverage warning',[('Partial archive',self.store.note),
                       ('Do not infer total currency supply','Balance updates show changes, not current account balances or total outstanding currency.')])

    def page_sources(self,p):
        self.title_line(p,'All income sources',
            'Every source is listed separately. Filter by category or cashflow and open a source to see its earnings, losses, players and original logs.')
        self.filter_panel(p)
        c=self.c
        rows=self.store.source_catalogue(self.filters)
        positives=sum(1 for r in rows if r['net']>0)
        negatives=sum(1 for r in rows if r['net']<0)
        self.stats_cards(p,[('Individual sources',len(rows),'Each game and income mechanism has its own row.','accent'),
            ('Net income sources',positives,'Sources with more credits than debits.','green'),
            ('Net cash sinks',negatives,'Sources with more debits than credits.','red'),
            ('Games tracked',len([r for r in rows if r['domain']=='Games']),'Click Games for stake and payout breakdowns.','text')])
        control=self.panel(p)
        bar=tk.Frame(control,bg=c['panel']);bar.pack(fill='x',padx=15,pady=14)
        tk.Label(bar,text='Category',fg=c['text'],bg=c['panel'],font=(FONT,10,'bold')).pack(side='left')
        domains=['All categories']+sorted(set(r['domain'] for r in rows))
        if self.source_domain.get() not in domains:self.source_domain.set('All categories')
        dc=ttk.Combobox(bar,textvariable=self.source_domain,values=domains,state='readonly',width=17)
        dc.pack(side='left',padx=(9,22))
        tk.Label(bar,text='Direction',fg=c['text'],bg=c['panel'],font=(FONT,10,'bold')).pack(side='left')
        sc=ttk.Combobox(bar,textvariable=self.source_sign,values=['All flows','Net income','Net loss','Break even'],state='readonly',width=15)
        sc.pack(side='left',padx=(9,22))
        tk.Button(bar,text='Show only games',command=lambda:self.navigate('games'),
                  **flat_button(c,True)).pack(side='right')
        self.section(p,'Individual source ledger','Select a row and click View details')
        panel=self.panel(p)
        table=DataGrid(panel,c,['domain','name','net','minted','burned','users','events'],rows,
            click_name='Sources: blackjack, work, Mafia matches, shops and more',
            labels={'domain':'Category','name':'Source','net':'Net impact','minted':'Credits to players',
                    'burned':'Debits from players','users':'Players','events':'Records'},
            on_open=self._source_open,height=20)
        table.pack(fill='x')
        note=tk.Label(panel,text='Net = credits minus debits. Positive net increases player balances; negative net removes money. Double-click or use View details.',
                bg=c['panel'],fg=c['muted'],font=(FONT,9),wraplength=900,justify='left')
        note.pack(anchor='w',padx=16,pady=(0,12))
        def update(*_):
            d=self.source_domain.get();direction=self.source_sign.get()
            subset=[r for r in rows if (d=='All categories' or r['domain']==d) and (
                direction=='All flows' or (direction=='Net income' and r['net']>0) or
                (direction=='Net loss' and r['net']<0) or (direction=='Break even' and r['net']==0))]
            table.set_rows(subset)
        dc.bind('<<ComboboxSelected>>',update)
        sc.bind('<<ComboboxSelected>>',update)
        update()
        self.text_panel(p,'How to read the categories',[
            ('Games','Each game is independent: Blackjack, Cockfight, Roulette, Russian Roulette, Slot Machine, Higher or Lower, and Animal Race. Payouts, bets and related purchases count toward the same game.'),
            ('Earnings','Separate methods such as Work, Crime, Slut, Role income, Chat activity and Robbery.'),
            ('Mafia and Shops','Mafia matches, hosting and quests are separate. Individual Mafia/regular shop items are available under Shop intelligence.'),
            ('Unclassified events','Unrecognized audit entries stay in their own category rather than being incorrectly attributed to a known income source. Transfers and admin changes are excluded by default.')])

    def page_games(self,p):
        self.title_line(p,'Individual games',
            "All casino games are separated here. Stakes, winnings and game-related purchases are combined into each game\'s net result.")
        self.filter_panel(p)
        c=self.c
        games=self.store.game_breakdown(self.filters)
        played=[r for r in games if r['events']]
        total_bets=sum(r['bets'] for r in played)
        total_stakes=sum(r['stakes'] for r in played)
        total_payouts=sum(r['payouts'] for r in played)
        total_net=sum(r['net'] for r in played)
        self.stats_cards(p,[('Games recorded',len(played),'Game types with activity in this period.','accent'),
            ('Bet records',money(total_bets),'One recorded bet is treated as one estimated play.','text'),
            ('Total stakes',money(total_stakes),'Money wagered, excluding separate game supplies.','text'),
            ('Total game net',money(total_net,True),'Combined game impact on user balances.','green' if total_net>=0 else 'red')])
        self.section(p,'Open a game','Choose a game below to see exact sources and recorded transactions')
        quick=self.panel(p)
        row=tk.Frame(quick,bg=c['panel']);row.pack(fill='x',padx=14,pady=13)
        for i,name in enumerate(GAME_NAMES):
            btn=tk.Button(row,text=name,command=lambda n=name:self.open_game(n),
                  **flat_button(c,True if name=='Blackjack' else False))
            btn.grid(row=i//4,column=i%4,sticky='ew',padx=5,pady=5)
        for i in range(4):row.grid_columnconfigure(i,weight=1)
        self.section(p,'Casino results','Select a game and press View details')
        panel=self.panel(p)
        table=DataGrid(panel,c,['name','net','bets','stakes','payouts','extra_costs','return_pct','net_per_bet','users'],games,
             labels={'name':'Game','net':'Player net','bets':'Bet records','stakes':'Stakes',
                     'payouts':'Winnings','extra_costs':'Supplies','return_pct':'Payout / stake %',
                     'net_per_bet':'Net / bet','users':'Players'},
             click_name='Every game, including low-volume games',on_open=self._source_open,height=12)
        table.pack(fill='x')
        tk.Label(panel,text='Positive Player net = currency added by the game. Negative = net loss to players. Payout / stake excludes supply costs and is not a theoretical probability.',
             bg=c['panel'],fg=c['muted'],font=(FONT,9),wraplength=900,justify='left').pack(anchor='w',padx=15,pady=(0,12))
        self.section(p,'Compare game impact')
        plot_panel=self.panel(p);chart=FlowChart(plot_panel,c,height=270)
        chart.pack(fill='x',padx=16,pady=15)
        chart.configure_data([(r['name'],r['net']) for r in games])
        self.text_panel(p,'Important distinctions',[
            ('Net includes all logged costs','Cockfight includes chicken purchases; Animal Race includes animal and provision purchases, not only wagers.'),
            ('Observed, not theoretical, returns','The displayed ratios describe actual transactions in the selected period. They are not calculated from the game engine or its theoretical odds.'),
            ('Player perspective','Net positive is good for players but creates currency. Net negative removes currency from players. Use Scenario lab to test adjustment ideas.')])

    def open_game(self,name):
        self.source_return='games'
        self.selected_source=name
        self.navigate('source_detail')

    def page_flows(self,p):
        self.title_line(p,'Income and sinks','Every source combines its positive payouts and negative costs. Expand the taxonomy by group.')
        self.filter_panel(p)
        domain=self.store.sources(self.filters,by='domain');sources=self.store.sources(self.filters)
        self.stats_cards(p,[('Sources',len(sources),'Distinct merged income/spending mechanisms.','text'),
         ('Groups',len(domain),'Higher-level categories.','accent'),
         ('Sources adding cash',sum(r['net']>0 for r in sources),'Positive net contributors.','green'),
         ('Sources taking cash',sum(r['net']<0 for r in sources),'Negative net contributors.','red')])
        buttons=tk.Frame(p,bg=self.c['bg']);buttons.pack(fill='x',padx=25,pady=(0,14))
        tk.Button(buttons,text='See every income source',command=lambda:self.navigate('sources'),
                  **flat_button(self.c,True)).pack(side='left',padx=(0,9))
        tk.Button(buttons,text='Open all seven games',command=lambda:self.navigate('games'),
                  **flat_button(self.c)).pack(side='left')
        self.grid(p,domain,['name','net','minted','burned','events','users'],'By major group',
             lambda row:self.show_domain(row['name']),height=8)
        self.grid(p,sources,['name','net','minted','burned','users','events'],'Sources ranked by absolute net impact',self._source_open,height=16)
        self.section(p,'Why grouping matters')
        self.text_panel(p,'Read sources as complete flows',[
           ('Gambling includes stakes and wins','An individual game is counted once as a net source. Chickens are included in Cockfight costs, and animals/provisions in Animal Race costs.'),
           ('Mafia shop is fully itemized','Every observed Mafia profile product is grouped consistently. Vouchers, tokens, colors, gradients, titles, death messages, voting messages, and custom orders are separate merchandise groups.'),
           ('Transferable money is not automatically new money','Give-money transfers and administrative changes are excluded by default, with explicit toggles above.')])

    def show_domain(self,name):
        self.selected_source=('domain',name);self.navigate('source_detail')

    def page_source_detail(self,p):
        target=self.selected_source
        if not target:self.navigate('flows');return
        is_domain=isinstance(target,tuple) and target[0]=='domain'
        if is_domain:
            f=dict(self.filters,domain=target[1]);label=target[1]
        elif isinstance(target,tuple) and target[0]=='identified':
            f=dict(self.filters,domain=target[1],source=target[2]);label=target[2]
        else:
            f=dict(self.filters,source=target);label=target
        destination='sources' if is_domain else self.source_return
        back_label={'games':'Games','sources':'All income sources','flows':'Flow summary'}.get(destination,'All income sources')
        self.title_line(p,label,'All gains and costs for this source in the selected period.',(back_label,destination))
        t=self.store.totals(f)
        self.stats_cards(p,[('Net impact',money(t['net'],True),'Actual net cash movement.','green' if t['net']>=0 else 'red'),
             ('Gross credits',money(t['minted']),'Payouts and refunds.','text'),
             ('Gross debits',money(t['burned']),'Bets and purchases.','text'),
             ('Participants',money(t['users']),'Unique people using this source.','accent')])
        if is_domain:
            # The parent group must show each INDIVIDUAL source, not only an
            # unhelpful aggregation of generic components such as stake/payout.
            self.section(p,'Sources within '+label,'Double-click any source for its full breakdown')
            self.grid(p,self.store.source_catalogue(f),['name','net','minted','burned','users','events'],
                      'Individual income and spending sources',self._source_open,height=15)
        if label in GAME_NAMES:
            game=next((r for r in self.store.game_breakdown(self.filters) if r['name']==label),None)
            if game:
                ret=('n/a' if game['return_pct'] is None else f"{game['return_pct']:.1f}%")
                per=('n/a' if game['net_per_bet'] is None else f"{game['net_per_bet']:+,.2f}")
                self.stats_cards(p,[('Logged bets',money(game['bets']),'One bet record approximates a play.','text'),
                    ('Total stakes',money(game['stakes']),'Sum of recorded wager debits.','red'),
                    ('Game payouts',money(game['payouts']),'Sum of logged game winnings.','green'),
                    ('Payout / stake',ret,'Observed payout/stake ratio, not theoretical odds.','accent')])
                self.text_panel(p,'Game economics',[
                    ('Net balance change per bet',per+' per logged bet. Includes game-related inventory costs where applicable.'),
                    ('Other game costs',money(game['extra_costs'])+' in supplies, provisions or animals.'),
                    ('Payout records',money(game['winning_events'])+' payout events versus '+money(game['bets'])+' recorded bets. These are logged events, not proven individual game sessions.')])
        self.grid(p,self.store.sources(f,by='component'),['name','net','minted','burned','events','users'],'Breakdown by transaction type',height=12)
        if label in ('Mafia profile shop','Regular item shop'):
            self.grid(p,self.store.items(f),['item_name','item_group','purchases','buyers','net_spend','avg_spend'],'Items within this source',self._item_open,height=12)
        if label in ('Role income','Chat activity'):
            self.grid(p,self.store.sources(f,by='reason'),['name','net','minted','burned','events'],
                'Breakdown by role or channel',height=12)
        if label in ('Animal Race','Cockfight'):
            self.grid(p,self.store.items(f),['item_name','item_group','purchases','net_spend'],
                'Associated purchases',self._item_open,height=8)
        self.grid(p,self.store.sources(f,by='user_id'),['name','net','minted','burned','events'],'Who earned or spent here',
            lambda r:self._user_open({'user_id':r['name']}),height=12)
        daily=self.store.timeseries(f,unit='day')
        self.section(p,'Daily net history')
        box=self.panel(p);plot=FlowChart(box,self.c,mode='line');plot.pack(fill='x',padx=15,pady=15)
        plot.configure_data([(r['period'],r['net']) for r in daily[-30:]],'line')
        self.grid(p,self.store.events(f,page_size=300),['utc','user_id','amount','component','reason'],'Original balance changes',height=14,
              opener=lambda r:self.show_event(r))

    def page_shops(self,p):
        self.title_line(p,'Shop intelligence','Individual item sales, popularity and buyer concentration, including every observed Mafia shop item.')
        c=self.c;top=self.panel(p)
        row=tk.Frame(top,bg=c['panel']);row.pack(fill='x',padx=16,pady=12)
        tk.Label(row,text='Store',bg=c['panel'],fg=c['muted']).pack(side='left')
        box=ttk.Combobox(row,textvariable=self.shop_view,state='readonly',values=['Mafia shop','Regular shop','Game purchases','All purchases'],width=19)
        box.pack(side='left',padx=(8,24));box.bind('<<ComboboxSelected>>',lambda e:self.navigate('shops'))
        tk.Label(row,text='Category',bg=c['panel'],fg=c['muted']).pack(side='left')
        typebox=ttk.Combobox(row,textvariable=self.shop_group,state='readonly',width=19)
        typebox.pack(side='left',padx=(8,20))
        tk.Label(row,text='Search',bg=c['panel'],fg=c['muted']).pack(side='left')
        search=self.small_entry(row,self.shop_search,19);search.pack(side='left',padx=9)
        shop={'Mafia shop':'mafia','Regular shop':'regular','Game purchases':'other','All purchases':'all'}.get(self.shop_view.get(),'mafia')
        items=self.store.items(self.filters,shop=shop)
        groups=sorted({r['item_group'] for r in items})
        typebox['values']=['All categories']+groups
        if self.shop_group.get() not in typebox['values']:self.shop_group.set('All categories')
        typebox.bind('<<ComboboxSelected>>',lambda e:draw())
        gross=sum(r['net_spend'] for r in items);buys=sum(r['purchases'] for r in items)
        self.stats_cards(p,[('Tracked items',money(len(items)),'Distinct products observed in this shop.','text'),
            ('Purchases',money(buys),'Observed purchase audit events.','text'),
            ('Net cash removed',money(gross),'Purchase debits less matching credits.','red'),
            ('Average purchase',money(gross/max(1,buys)),'Mean recorded purchase price.','accent')])
        self.section(p,'Item catalogue','Double-click an item for buyers and purchase history')
        host=self.panel(p)
        grid=DataGrid(host,c,['item_name','item_group','purchases','buyers','net_spend','avg_spend','last_purchase'],items,
                        click_name='Products by actual spending',on_open=self._item_open,height=20)
        grid.pack(fill='x')
        def draw(*_):
            subset=[r for r in items if (self.shop_group.get()=='All categories' or r['item_group']==self.shop_group.get())
                and self.shop_search.get().casefold() in (r['item_name']+' '+r['item_id']).casefold()]
            grid.set_rows(subset)
        search.bind('<KeyRelease>',lambda e:draw())
        draw()
        groups=self.store.items(self.filters,shop=shop)
        group_sum=defaultdict(lambda:[0,0])
        for r in groups:
            group_sum[r['item_group']][0]+=r['purchases'];group_sum[r['item_group']][1]+=r['net_spend']
        self.grid(p,[{'name':k,'purchases':v[0],'net_spend':v[1]} for k,v in sorted(group_sum.items(),key=lambda x:-x[1][1])],
                 ['name','purchases','net_spend'],'Spending by item category',height=10)

    def page_item_detail(self,p):
        if not self.selected_item:self.navigate('shops');return
        source,key,name=self.selected_item
        f=dict(self.filters,source=source,item_id=key)
        self.title_line(p,name,'Shop item performance and purchase history.',('Back to shops','shops'))
        total=self.store.totals(f)
        buyers=self.store.item_users(key,source,self.filters)
        for row in buyers:row['display_name']=self.store.user_label(row['user_id'])
        entries=self.store.events(f,page_size=500)
        dates=[r['utc'] for r in entries]
        self.stats_cards(p,[('Net spent',money(-total['net']),'Charges less refunds.','red'),
            ('Purchases',money(total['events']),'Observed purchase entries.','text'),
            ('Unique buyers',money(len(buyers)),'Distinct purchasing accounts.','accent'),
            ('Average cost',money(-total['net']/max(1,total['events'])),'Average net debit per event.','text')])
        self.grid(p,buyers,['display_name','user_id','purchases','spent','last_purchase'],'Item buyer leaderboard',self._user_open,height=14)
        self.grid(p,entries,['utc','user_id','amount','component','reason'],'Every recorded purchase',self.show_event,height=18)

    def page_users(self,p):
        self.title_line(p,'Members','Observed net earnings, spending, participation and transaction frequency by account.')
        self.filter_panel(p)
        users=self.store.users(self.filters)
        for u in users:u['display_name']=self.store.user_label(u['user_id'])
        profitable=sum(u['net']>0 for u in users)
        self.stats_cards(p,[('Accounts',money(len(users)),'Observed active accounts.','text'),
             ('Net positive',money(profitable),'Players gaining net money.','green'),
             ('Net negative',money(sum(u['net']<0 for u in users)),'Players losing net money.','red'),
             ('Max active days',money(max((u['active_days'] for u in users),default=0)),'Observed participation days.','accent')])
        self.grid(p,users,['display_name','user_id','net','minted','burned','active_days','active_5m','events','last'],
                  'Member ledger (sort headers to compare)',self._user_open,height=23)
        self.text_panel(p,'Activity estimate caveat',[
            ('Five-minute activity blocks','One transaction in any five-minute block counts the entire block as observed economy activity. This is not Discord presence or actual playtime.'),
            ('Net earnings are not wealth','The source contains changes, not full balances. Member net gain since the selected start date is not their current balance.')])

    def page_user_detail(self,p):
        if not self.selected_user:self.navigate('users');return
        f=dict(self.filters,user=self.selected_user)
        t=self.store.totals(f)
        self.title_line(p,'Member '+self.store.user_label(self.selected_user),'Observed economy activity and source breakdown. ID: '+self.selected_user,('Back to members','users'))
        self.stats_cards(p,[('Net result',money(t['net'],True),'Across selected interval.','green' if t['net']>=0 else 'red'),
            ('Credits',money(t['minted']),'Gross additions.','text'),('Debits',money(t['burned']),'Gross deductions.','text'),
            ('Events',money(t['events']),'Balance update entries.','accent')])
        self.grid(p,self.store.sources(f),['name','net','minted','burned','events'],'Member income and spending by source',self._source_open,height=14)
        self.grid(p,self.store.events(f,page_size=400),['utc','amount','source','component','reason'],'Member audit trail',self.show_event,height=22)

    def page_trends(self,p):
        self.title_line(p,'Trends and seasonality','Measured history, not predicted player behavior. Compare cash creation, removal and activity.')
        c=self.c;control=self.panel(p)
        row=tk.Frame(control,bg=c['panel']);row.pack(fill='x',padx=16,pady=14)
        tk.Label(row,text='Aggregation',bg=c['panel'],fg=c['text']).pack(side='left')
        select=ttk.Combobox(row,textvariable=self.chart_unit,values=['Hourly','Daily','Monthly'],state='readonly',width=17)
        select.pack(side='left',padx=14);select.bind('<<ComboboxSelected>>',lambda e:self.navigate('trends'))
        gran={'Hourly':'hour','Daily':'day','Monthly':'month'}[self.chart_unit.get()]
        timeline=self.store.timeseries(self.filters,unit=gran)
        if not timeline:return
        self.stats_cards(p,[('Periods',len(timeline),'Data points available.','text'),
           ('Largest net rise',money(max(r['net'] for r in timeline),True),'Peak recorded period.','green'),
           ('Largest net fall',money(min(r['net'] for r in timeline),True),'Largest net reduction.','red'),
           ('Mean net period',money(sum(r['net'] for r in timeline)/len(timeline),True),'Average change per time bucket.','text')])
        for title,metric,mode in [('Net movement','net','line'),('Money minted','minted','bars'),('Money removed','burned','bars'),('Active accounts','users','line')]:
            self.section(p,title)
            box=self.panel(p);chart=FlowChart(box,c,mode=mode,height=245);chart.pack(fill='x',padx=15,pady=16)
            chart.configure_data([(r['period'],r[metric]) for r in timeline[-32:]],mode)
        self.grid(p,timeline,['period','net','minted','burned','events','users'],'Exportable trend records',height=17)

    def page_activity(self,p):
        self.title_line(p,'Activity and macro detection','A continuous 24-hour five-minute-block streak is a review signal, not proof of automation.')
        self.filter_panel(p)
        if not hasattr(self,'macro_rows'):
            box=self.panel(p)
            tk.Label(box,text='Run economy-activity scan',bg=self.c['panel'],fg=self.c['text'],font=(FONT,14,'bold')).pack(anchor='w',padx=18,pady=(18,5))
            tk.Label(box,text='Analyzes all users as distinct five-minute UTC buckets. 288 consecutive active blocks triggers a review flag.',
                bg=self.c['panel'],fg=self.c['muted'],wraplength=850).pack(anchor='w',padx=18)
            tk.Button(box,text='Scan transaction activity',command=self.run_macro_scan,**flat_button(self.c,True)).pack(anchor='w',padx=18,pady=17)
            return
        rows=self.macro_rows
        flagged=sum(r['flagged'] for r in rows)
        self.stats_cards(p,[('Reviewed accounts',money(len(rows)),'Users with transactions.','text'),
             ('Flagged accounts',money(flagged),'288 uninterrupted five-minute blocks.','red'),
             ('Max streak',f"{max((r['longest_hours'] for r in rows),default=0):.1f} h",'Longest inferred continuous period.','amber'),
             ('Review threshold','24 hours','Transaction-block activity only.','text')])
        self.grid(p,rows,['user_id','flagged','longest_hours','active_blocks','streak_start'],
                  'Longest active block streak by account',self._user_open,height=25)
        self.text_panel(p,'Correct interpretation',[
            ('Estimated, not actual time','A record appearing in every five-minute window suggests sustained activity, but does not establish continuous Discord use or macro use.'),
            ('Not a punishment tool','Inspect command patterns and context before taking any action.')])

    def run_macro_scan(self):
        self.status.set('Scanning consecutive 5-minute blocks...')
        f=dict(self.filters)
        def task():
            try:self.messages.put(('macro',self.store.suspicious_activity(f)))
            except Exception as e:self.messages.put(('macro_error',str(e)))
        threading.Thread(target=task,daemon=True).start()

    def show_event(self,row):
        """Show a readable transaction summary without exposing raw DHT JSON."""
        c=self.c
        top=tk.Toplevel(self)
        top.title('Transaction details')
        top.geometry('690x500')
        top.configure(bg=c['panel'])
        top.transient(self)
        tk.Label(top,text='Transaction details',bg=c['panel'],fg=c['text'],
                 font=(FONT,18,'bold')).pack(anchor='w',padx=22,pady=(20,5))
        tk.Label(top,text='A single recorded change to a member balance.',bg=c['panel'],
                 fg=c['muted'],font=(FONT,10)).pack(anchor='w',padx=22,pady=(0,15))
        fields=[
            ('Date and time',utc_display(row.get('utc',''))),
            ('Member',self.store.user_label(row.get('user_id',''))),
            ('Net balance change',money(row.get('amount',0),True)),
            ('Category',row.get('domain','')),
            ('Income source',row.get('source','')),
            ('Transaction type',row.get('component','')),
            ('Cash change',money(row.get('cash',0),True)),
            ('Bank change',money(row.get('bank',0),True)),
            ('Activity description',row.get('reason','')),
        ]
        body=tk.Frame(top,bg=c['panel'])
        body.pack(fill='both',expand=True,padx=22,pady=(0,15))
        for index,(label,value) in enumerate(fields):
            line=tk.Frame(body,bg=c['panel2'] if index%2==0 else c['panel'])
            line.pack(fill='x')
            tk.Label(line,text=label,bg=line['bg'],fg=c['muted'],font=(FONT,9,'bold'),
                     width=19,anchor='w',padx=10,pady=8).pack(side='left')
            tk.Label(line,text=str(value),bg=line['bg'],fg=c['text'],font=(FONT,10),
                     anchor='w',justify='left',wraplength=430,padx=10,pady=8).pack(side='left',fill='x',expand=True)
        tk.Button(top,text='Close',command=top.destroy,**flat_button(c,True)).pack(anchor='e',padx=22,pady=(0,18))

    def page_scenario(self,p):
        self.title_line(p,'Scenario lab','Experiment with payout, cost and activity multipliers. Observed behavior is held constant.')
        c=self.c
        self.text_panel(p,'What this model does',[
            ('Counterfactual on recorded events','Changes are applied to historical positive and negative balance movements, then scaled to 30 days.'),
            ('What this model does not do','It does not assume people buy equally often after price changes, or that game odds stay unchanged after rule changes.'),
            ('Confidence interval','Bootstrap samples whole members (not individual transactions) to estimate uncertainty in the observed member mix.')])
        controls=self.panel(p)
        title=tk.Frame(controls,bg=c['panel']);title.pack(fill='x',padx=16,pady=(15,8))
        tk.Label(title,text='Add a scenario rule',bg=c['panel'],fg=c['text'],font=(FONT,13,'bold')).pack(anchor='w')
        line=tk.Frame(controls,bg=c['panel']);line.pack(fill='x',padx=16,pady=(0,10))
        tk.Label(line,text='Target kind',bg=c['panel'],fg=c['muted']).pack(side='left')
        scope=ttk.Combobox(line,textvariable=self.selected_scope,values=['Source','Group','Mafia item','Regular item','Any item'],
             state='readonly',width=14);scope.pack(side='left',padx=(7,16))
        tk.Label(line,text='Target',bg=c['panel'],fg=c['muted']).pack(side='left')
        targets=ttk.Combobox(line,textvariable=self.selected_target,width=35,state='readonly')
        targets.pack(side='left',padx=7,fill='x',expand=True)
        def update_targets(*_):
            selected=self.selected_scope.get()
            self.scenario_item_keys={}
            if selected=='Source':
                values=[r['name'] for r in self.store.sources(self.filters)]
            elif selected=='Group':
                values=[r['name'] for r in self.store.sources(self.filters,by='domain')]
            else:
                v={'Mafia item':'mafia','Regular item':'regular','Any item':'all'}.get(selected,'all')
                values=[]
                for item in self.store.items(self.filters,shop=v):
                    label=item['item_name'] or 'Unnamed item'
                    if label in values:
                        label=f"{label} ({item['item_group']})"
                    if label in values:
                        label=f"{label} - {item['source']}"
                    base=label
                    suffix=2
                    while label in values:
                        label=f"{base} #{suffix}"
                        suffix+=1
                    values.append(label)
                    self.scenario_item_keys[label]=item['item_id']
            targets['values']=values
            if values and self.selected_target.get() not in values:self.selected_target.set(values[0])
        scope.bind('<<ComboboxSelected>>',update_targets);update_targets()
        rates=tk.Frame(controls,bg=c['panel']);rates.pack(fill='x',padx=16,pady=(7,10))
        self.sim_payout=tk.StringVar(value='100');self.sim_cost=tk.StringVar(value='100');self.sim_volume=tk.StringVar(value='100')
        for name,var,tip in [('Positive payouts %',self.sim_payout,'100 = unchanged rewards.'),
           ('Negative costs %',self.sim_cost,'110 = 10 percent larger debits.'),
           ('Transaction volume %',self.sim_volume,'90 = 10 percent fewer events with the same mix.')]:
            wrap=tk.Frame(rates,bg=c['panel']);wrap.pack(side='left',padx=(0,24))
            label=tk.Label(wrap,text=name,bg=c['panel'],fg=c['muted'],font=(FONT,9));label.pack(anchor='w')
            inp=self.small_entry(wrap,var,13);inp.pack(anchor='w',ipady=4,pady=4);HoverTip(label,tip)
        btns=tk.Frame(controls,bg=c['panel']);btns.pack(fill='x',padx=16,pady=(0,15))
        tk.Button(btns,text='Add rule',command=self.add_rule,**flat_button(c,True)).pack(side='left')
        tk.Button(btns,text='Clear rules',command=self.clear_rules,**flat_button(c)).pack(side='left',padx=8)
        tk.Button(btns,text='Run simulation',command=self.run_scenario,**flat_button(c,True)).pack(side='right')
        tk.Button(btns,text='Save scenario',command=self.save_scenario,**flat_button(c)).pack(side='right',padx=7)
        tk.Button(btns,text='Load scenario',command=self.load_scenario,**flat_button(c)).pack(side='right')
        self.section(p,'Auto-balance assistant')
        assistant=self.panel(p)
        autoline=tk.Frame(assistant,bg=c['panel']);autoline.pack(fill='x',padx=15,pady=15)
        tk.Label(autoline,text='30-day target net',bg=c['panel'],fg=c['text']).pack(side='left')
        self.balance_goal=tk.StringVar(value='0')
        self.small_entry(autoline,self.balance_goal,15).pack(side='left',padx=(9,18),ipady=5)
        tk.Label(autoline,text='Maximum change per lever',bg=c['panel'],fg=c['text']).pack(side='left')
        self.balance_cap=tk.StringVar(value='20')
        self.small_entry(autoline,self.balance_cap,8).pack(side='left',padx=(9,7),ipady=5)
        tk.Label(autoline,text='%',bg=c['panel'],fg=c['muted']).pack(side='left')
        tk.Button(autoline,text='Suggest balanced rules',command=self.auto_balance,
                  **flat_button(c,True)).pack(side='right')
        tk.Label(assistant,text='Finds a mix of bounded reward and shop-price adjustments. Does not change your actual economy or assume demand will stay constant.',
            bg=c['panel'],fg=c['muted'],font=(FONT,9),wraplength=950).pack(anchor='w',padx=15,pady=(0,14))
        self.section(p,'Quick experiment presets')
        presetbar=self.panel(p)
        inner=tk.Frame(presetbar,bg=c['panel']);inner.pack(fill='x',padx=14,pady=12)
        for title,action in [('15% less work income',lambda:self.preset('source','Work',.85,1)),
          ('10% higher shop costs',lambda:self.preset('domain','Shops',1,1.10)),
          ('10% higher Mafia shop costs',lambda:self.preset('source','Mafia profile shop',1,1.10)),
          ('5% lower game payouts',lambda:self.preset('domain','Games',.95,1))]:
            tk.Button(inner,text=title,command=action,**flat_button(c)).pack(side='left',padx=(0,9))
        self.rules_host=tk.Frame(p,bg=c['bg']);self.rules_host.pack(fill='x')
        self.result_host=tk.Frame(p,bg=c['bg']);self.result_host.pack(fill='x')
        self.paint_rules()
        if self.last_sim:self.paint_scenario()

    def add_rule(self):
        try:
            payouts=[float(self.sim_payout.get())/100,float(self.sim_cost.get())/100,float(self.sim_volume.get())/100]
            if any(not math.isfinite(x) or x<0 or x>5 for x in payouts):raise ValueError('Use multipliers between 0% and 500%.')
            scope='domain' if self.selected_scope.get()=='Group' else 'source' if self.selected_scope.get()=='Source' else 'item'
            displayed=self.selected_target.get()
            key=self.scenario_item_keys.get(displayed) if scope=='item' else displayed
            if not key:raise ValueError('Select a target.')
            rule={'scope':scope,'key':key,'payout':payouts[0],'cost':payouts[1],'volume':payouts[2]}
            if scope=='item':rule['label']=displayed
            self.rules.append(rule)
            self.last_sim=None;self.paint_rules();self.paint_scenario()
        except ValueError as e:messagebox.showwarning('Invalid scenario rule',str(e),parent=self)

    def preset(self,scope,key,payout,cost):
        self.rules=[{'scope':scope,'key':key,'payout':payout,'cost':cost,'volume':1}]
        self.last_sim=None;self.paint_rules();self.paint_scenario()

    def clear_rules(self):
        self.rules=[];self.last_sim=None;self.paint_rules();self.paint_scenario()

    def paint_rules(self):
        if not hasattr(self,'rules_host'):return
        for w in self.rules_host.winfo_children():w.destroy()
        self.section(self.rules_host,'Active model rules')
        data=[{'scope':r['scope'].title(),'target':r.get('label',r['key']),'payout':f"{r['payout']*100:.0f}%",
          'cost':f"{r['cost']*100:.0f}%",'volume':f"{r['volume']*100:.0f}%"} for r in self.rules]
        host=self.panel(self.rules_host)
        if not data:
            tk.Label(host,text='No changes yet. The baseline scenario matches the observed data.',
              bg=self.c['panel'],fg=self.c['muted'],font=(FONT,10)).pack(anchor='w',padx=15,pady=17)
        else:
            grid=DataGrid(host,self.c,['scope','target','payout','cost','volume'],data,click_name='Double-click a rule to remove it',height=6,
                on_open=lambda row:self.remove_rule(data.index(row)))
            grid.pack(fill='x')

    def remove_rule(self,index):
        if 0<=index<len(self.rules):self.rules.pop(index)
        self.last_sim=None;self.paint_rules();self.paint_scenario()

    def run_scenario(self):
        try:self.last_sim=self.store.simulate(self.rules,self.filters,horizon=30)
        except Exception as e:messagebox.showerror('Simulation failed',str(e),parent=self);return
        self.paint_scenario()

    def paint_scenario(self):
        if not hasattr(self,'result_host'):return
        for w in self.result_host.winfo_children():w.destroy()
        if not self.last_sim:return
        data=self.last_sim
        self.section(self.result_host,'30-day counterfactual')
        self.stats_cards(self.result_host,[('Observed-rate baseline',money(data['before'],True),'Historical net pace scaled to 30 days.','text'),
            ('Proposed rate',money(data['after'],True),'Counterfactual 30-day net movement.','text'),
            ('Difference',money(data['change'],True),'Positive means more user money created.','green' if data['change']>0 else 'red'),
            ('Sampled users',money(data['users']),'Bootstrap unit is one member.','accent')])
        if data['ci']:
            low,high=data['ci']
            self.text_panel(self.result_host,'Uncertainty for 30-day change',[
                ('95% member-bootstrap interval',f'{money(low,True)} to {money(high,True)} currency per 30 days.'),
                ('Important assumption','Uses the observed member mix. It does not capture changes in demand or player responses to altered rewards or costs.')])
        self.grid(self.result_host,sorted((r for r in data['sources'] if r['change']),key=lambda x:-abs(x['change'])),
            ['source','before','after','change'],'Most affected income sources',height=16)

    def auto_balance(self):
        try:
            goal=float(self.balance_goal.get().replace(',',''))
            cap=float(self.balance_cap.get())/100
            candidate=self.store.recommend_rebalance(self.filters,goal,cap)
            self.rules=candidate['rules']
            self.last_sim=self.store.simulate(self.rules,self.filters,horizon=30)
            self.paint_rules();self.paint_scenario()
            self.status.set('Auto-balance tested. Remaining target gap: '+money(candidate['remainder'],True))
        except Exception as e:
            messagebox.showerror('Could not calculate rebalance',str(e),parent=self)

    def save_scenario(self):
        path=filedialog.asksaveasfilename(parent=self,filetypes=[('JSON','*.json')],defaultextension='.json')
        if path:
            try:Path(path).write_text(json.dumps({'schema':1,'rules':self.rules},indent=2),encoding='utf8')
            except OSError as e:messagebox.showerror('Save failed',str(e),parent=self)

    def load_scenario(self):
        path=filedialog.askopenfilename(parent=self,filetypes=[('JSON','*.json')])
        if not path:return
        try:
            rules=json.loads(Path(path).read_text(encoding='utf8'))['rules']
            if not isinstance(rules,list):raise ValueError('Expected rules list.')
            known_item_names={item['item_id']:item['item_name'] for item in self.store.items(self.filters,shop='all')}
            for r in rules:
                if r['scope'] not in ('domain','source','item'):raise ValueError('Invalid scope')
                if not str(r['key']):raise ValueError('Missing key')
                for field in ('payout','cost','volume'):
                    if not 0<=float(r[field])<=5:raise ValueError('Invalid multiplier')
                if r['scope']=='item':
                    r.setdefault('label',known_item_names.get(r['key'],'Selected shop item'))
            self.rules=rules;self.last_sim=None;self.paint_rules();self.paint_scenario()
        except Exception as e:messagebox.showerror('Scenario file invalid',str(e),parent=self)



def main():
    app=EconomyStudio()
    app.mainloop()

if __name__=='__main__':main()
