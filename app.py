import os
import tkinter as tk
from tkinter import ttk,messagebox,colorchooser
from PIL import ImageTk
from generator import make,preview,export,available_fonts,DEFAULT_FONT
import preferences
from batch import export_batch,validate_batch
from plate_preview import render_plate
import copy
saved=preferences.load()

root=tk.Tk();root.title('三位置姓名牌生成器 v2.2 · 整盘预览')
root.geometry(f'{min(900,root.winfo_screenwidth()-80)}x{min(800,root.winfo_screenheight()-120)}')
root.minsize(560,400)
# Reserve the action bar before allocating the remaining height to content.
actions=ttk.Frame(root,padding=(12,8));actions.pack(side='bottom',fill='x')
body=ttk.Frame(root);body.pack(fill='both',expand=True)
left=ttk.Frame(body);left.pack(side='left',fill='both',expand=True)
canvas=tk.Canvas(left,highlightthickness=0,width=420)
scrollbar=ttk.Scrollbar(left,orient='vertical',command=canvas.yview)
scrollbar.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
canvas.configure(yscrollcommand=scrollbar.set)
form=ttk.Frame(canvas,padding=16)
form_window=canvas.create_window((0,0),window=form,anchor='nw')
form.bind('<Configure>',lambda event:canvas.configure(scrollregion=canvas.bbox('all')))
canvas.bind('<Configure>',lambda event:canvas.itemconfigure(form_window,width=event.width))
def wheel(event):
    under=root.winfo_containing(event.x_root,event.y_root)
    if under is not None and (str(under).startswith(str(left))):
        canvas.yview_scroll(-int(event.delta/120),'units')
root.bind('<MouseWheel>',wheel,add='+')
# ttk.Label(form,text='输入三处文字，生成双色 3MF',font=('Microsoft YaHei',14,'bold')).pack(anchor='w',pady=(0,24))
entries=[]
for title,value in zip(['① 顶部小字（最多 5 字）','② 姓名（最多 5 字，双字自动留空）','③ 底部（每列最多 4 字，双列用空格分隔）'],saved['texts']):
    ttk.Label(form,text=title).pack(anchor='w',pady=(12,4));v=tk.StringVar(value=value);entries.append(v)
    ttk.Entry(form,textvariable=v,font=('Microsoft YaHei',14),width=27).pack(anchor='w')
# ttk.Label(form,text='-------',wraplength=50).pack(anchor='w',pady=24)
font_vars=[]
for title,value in zip(['顶部字体','姓名字体','底部字体'],saved['fonts']):
    row=ttk.Frame(form);row.pack(anchor='w',pady=4)
    ttk.Label(row,text=title).pack(side='left',padx=(0,8))
    variable=tk.StringVar(value=value if value in available_fonts() else DEFAULT_FONT);font_vars.append(variable)
    picker=ttk.Combobox(row,textvariable=variable,values=available_fonts(),state='readonly',width=23)
    picker.pack(side='left');picker.bind('<<ComboboxSelected>>',lambda event:update())
ttk.Label(form,text='楷体、宋体、行楷细笔画较多，请检查切片预览。',wraplength=360).pack(anchor='w')
colors=saved['colors']
colorbar=ttk.Frame(form);colorbar.pack(fill='x',pady=6)
swatches=[]
def choose_color(i):
    result=colorchooser.askcolor(color=colors[i],title='底板颜色' if i==0 else '文字颜色',parent=root)
    if not result[1]:return
    colors[i]=result[1].upper();swatches[i].configure(bg=colors[i],activebackground=colors[i]);schedule_save();update()
for i,title in enumerate(['底板颜色','文字颜色']):
    row=ttk.Frame(colorbar);row.pack(side='left',padx=(0,18))
    ttk.Label(row,text=title).pack(side='left',padx=(0,6))
    button=tk.Button(row,bg=colors[i],activebackground=colors[i],width=5,height=1,command=lambda i=i:choose_color(i))
    button.pack(side='left');swatches.append(button)
# ttk.Label(form,text='点击色块打开调色盘；颜色随 3MF 一起保存。',wraplength=350).pack(anchor='w',pady=4)
previews=ttk.Notebook(body);previews.pack(side='right',fill='y',padx=8)
single_tab=ttk.Frame(previews);plate_tab=ttk.Frame(previews)
previews.add(single_tab,text='当前单块');previews.add(plate_tab,text='整盘预览')
label=ttk.Label(single_tab);label.pack(expand=True)
plate_label=ttk.Label(plate_tab);plate_label.pack(expand=True)
plate_picture=None
large_window=None
large_label=None
def enlarge_plate():
    global large_window,large_label
    if large_window is None or not large_window.winfo_exists():
        large_window=tk.Toplevel(root);large_window.title('整盘放大预览 · 可滚动查看')
        large_window.geometry(f'650x{min(900,root.winfo_screenheight()-120)}')
        c=tk.Canvas(large_window,highlightthickness=0);s=ttk.Scrollbar(large_window,orient='vertical',command=c.yview)
        s.pack(side='right',fill='y');c.pack(fill='both',expand=True);c.configure(yscrollcommand=s.set)
        large_label=ttk.Label(c);c.create_window((0,0),window=large_label,anchor='nw')
        large_label.bind('<Configure>',lambda e:c.configure(scrollregion=c.bbox('all')))
        large_window.bind('<MouseWheel>',lambda e:c.yview_scroll(-int(e.delta/120),'units'))
    picture=ImageTk.PhotoImage(plate_picture);large_label.configure(image=picture);large_label.image=picture;large_window.lift()
ttk.Button(plate_tab,text='放大查看整盘',command=enlarge_plate).pack(pady=8)
def refresh_plate():
    global plate_picture
    plate_picture=render_plate(batch_items)
    picture=ImageTk.PhotoImage(plate_picture.resize((300,500)));plate_label.configure(image=picture);plate_label.image=picture
    previews.tab(plate_tab,text=f'整盘预览 {len(batch_items)}/9')
    if large_window is not None and large_window.winfo_exists():
        p=ImageTk.PhotoImage(plate_picture);large_label.configure(image=p);large_label.image=p
status=tk.StringVar(value='点击预览检查排版，然后生成文件。');ttk.Label(form,textvariable=status,wraplength=340).pack(anchor='w',pady=12)
batch_items=[]
for item in saved.get('batch',[]):
    try:validate_batch(batch_items+[item]);batch_items.append(item)
    except (ValueError,KeyError,TypeError):pass
ttk.Label(form,text='本盘清单（最多9块；加入时保存当前文字/字体/颜色）').pack(anchor='w')
batch_list=tk.Listbox(form,height=5,exportselection=False);batch_list.pack(fill='x',pady=5)
def current_template():return {'texts':[v.get() for v in entries],'fonts':[v.get() for v in font_vars],'colors':list(colors)}
def refresh_batch():
    batch_list.delete(0,'end')
    for i,item in enumerate(batch_items):batch_list.insert('end',f'{i+1}. {item["texts"][0]} · {item["texts"][1]} · {item["texts"][2]}')
    refresh_plate()
def add_item():
    try:
        item=current_template();validate_batch(batch_items+[item]);batch_items.append(copy.deepcopy(item));refresh_batch();previews.select(plate_tab);schedule_save();status.set(f'本盘已加入 {len(batch_items)}/9 块。')
    except ValueError as e:messagebox.showerror('本盘提示',str(e))
def load_item():
    selected=batch_list.curselection()
    if not selected:return
    item=batch_items[selected[0]]
    for v,text in zip(entries,item['texts']):v.set(text)
    for v,font in zip(font_vars,item['fonts']):v.set(font)
    colors[:]=item['colors']
    for i,b in enumerate(swatches):b.configure(bg=colors[i],activebackground=colors[i])
    previews.select(single_tab)
    update()
def replace_item():
    selected=batch_list.curselection()
    if not selected:return
    try:
        updated=copy.deepcopy(batch_items);updated[selected[0]]=current_template();validate_batch(updated);batch_items[:]=updated;refresh_batch();previews.select(plate_tab);schedule_save()
    except ValueError as e:messagebox.showerror('本盘提示',str(e))
def remove_item():
    selected=batch_list.curselection()
    if selected:batch_items.pop(selected[0]);refresh_batch();schedule_save()
buttons=ttk.Frame(form);buttons.pack(fill='x')
for title,command in [('加入本盘',add_item),('载入选中',load_item),('更新选中',replace_item),('移除选中',remove_item)]:ttk.Button(buttons,text=title,command=command).pack(side='left')
refresh_batch()
def update():
    try:
        m,_=make(*(v.get() for v in entries),font_name=[v.get() for v in font_vars]);im=ImageTk.PhotoImage(preview(m,*colors).resize((270,495)));label.configure(image=im);label.image=im;status.set('25 × 50 mm，总厚 3.0 mm。\n文字从 2 mm 开始，嵌入 0.4 mm、凸出 0.6 mm。\n顶部圆角通孔：约 13.75 × 2.5 mm。');return True
    except ValueError as e:messagebox.showerror('输入提示',str(e));return False
def save():
    if not update():return
    try:
        path=export(*(v.get() for v in entries),base_color=colors[0],text_color=colors[1],font_name=[v.get() for v in font_vars]);status.set('已保存：'+str(path));os.startfile(str(path.parent))
    except Exception as e:messagebox.showerror('生成失败',str(e))
def save_batch():
    try:
        path=export_batch(copy.deepcopy(batch_items));status.set('整盘已保存：'+str(path));os.startfile(str(path.parent))
    except Exception as e:messagebox.showerror('整盘生成失败',str(e))
preview_button=ttk.Button(actions,text='预览当前',command=update)
preview_button.pack(side='left',padx=(0,12),ipady=6)
ttk.Button(actions,text='生成当前单块',command=save).pack(side='left',ipady=6,padx=(0,8))
generate_button=ttk.Button(actions,text='生成整盘 3MF',command=save_batch)
generate_button.pack(side='right',fill='x',expand=True,ipady=6)
pending_save=None
def persist():
    global pending_save
    pending_save=None
    try:preferences.save({'texts':[v.get() for v in entries],'fonts':[v.get() for v in font_vars],'colors':list(colors),'batch':copy.deepcopy(batch_items)})
    except OSError as e:status.set('设置保存失败：'+str(e))
def schedule_save(*args):
    global pending_save
    if pending_save is not None:root.after_cancel(pending_save)
    pending_save=root.after(350,persist)
for variable in entries+font_vars:variable.trace_add('write',schedule_save)
def close():
    if pending_save is not None:root.after_cancel(pending_save)
    persist();root.destroy()
root.protocol('WM_DELETE_WINDOW',close)
update();root.mainloop()
