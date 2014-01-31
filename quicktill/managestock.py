"""Implements the 'Manage Stock' menu."""

from __future__ import unicode_literals
import curses,curses.ascii,time
from . import ui,td,keyboard,printer,user,usestock
from . import stock,delivery,department,stocklines,stocktype
from .models import Department,FinishCode,StockLine,StockType
from .models import StockItem,Delivery,StockOut,func,desc
from sqlalchemy.orm import lazyload,undefer
import datetime

import logging
log=logging.getLogger(__name__)
from functools import reduce

def finish_reason(item,reason):
    stockitem=td.s.merge(item)
    stockitem.finished=datetime.datetime.now()
    stockitem.finishcode_id=reason
    stockitem.displayqty=None
    stockitem.stocklineid=None
    td.s.flush()
    log.info("Stock: finished item %d reason %s"%(stockitem.id,reason))
    ui.infopopup(["Stock item %d is now finished."%stockitem.id],
                 dismiss=keyboard.K_CASH,
                 title="Stock Finished",colour=ui.colour_info)

def finish_item(item):
    sfl=td.s.query(FinishCode).all()
    fl=[(x.description,finish_reason,(item,x.id)) for x in sfl]
    ui.menu(fl,blurb="Please indicate why you are finishing stock number %d:"%
            item.id,title="Finish Stock",w=60)

@user.permission_required('finish-unconnected-stock',
                          'Finish stock not currently on sale')
def finishstock(dept=None):
    """
    Finish stock not currently on sale."

    """
    log.info("Finish stock not currently on sale")
    stock.stockpicker(finish_item,title="Finish stock not currently on sale",
                      filter=stock.stockfilter(allow_on_sale=False),
                      check_checkdigits=False)

def print_stocklist_menu(sinfo,title):
    td.s.add_all(sinfo)
    if printer.labeldriver is not None:
        menu=[
            (keyboard.K_ONE,"Print list",
             printer.print_stocklist,(sinfo,title)),
            (keyboard.K_TWO,"Print sticky labels",
             printer.stocklabel_print,(sinfo,)),
            ]
        ui.keymenu(menu,"Stock print options",colour=ui.colour_confirm)
    else:
        printer.print_stocklist(sinfo,title)

def stockdetail(sinfo):
    # We are now passed a list of StockItem objects
    td.s.add_all(sinfo)
    if len(sinfo)==1:
        return stock.stockinfo_popup(sinfo[0].id)
    f=ui.tableformatter(' r l l ')
    sl=[(ui.tableline(f,(x.id,x.stocktype.format(),x.remaining_units)),
         stock.stockinfo_popup,(x.id,)) for x in sinfo]
    ui.menu(sl,title="Stock Detail",blurb="Select a stock item and press "
            "Cash/Enter for more information.",
            dismiss_on_select=False,keymap={
            keyboard.K_PRINT: (
                print_stocklist_menu,(sinfo,"Stock Check"),False)},
            colour=ui.colour_confirm)

@user.permission_required('stock-check','List unfinished stock items')
def stockcheck(dept=None):
    # Build a list of all not-finished stock items.
    log.info("Stock check")
    sq=td.s.query(StockItem).join(StockItem.stocktype).\
        join(Delivery).\
        filter(StockItem.finished==None).\
        filter(Delivery.checked==True).\
        order_by(StockItem.id)
    if dept: sq=sq.filter(StockType.dept_id==dept)
    sinfo=sq.all()
    # Split into groups by stocktype
    st={}
    for s in sinfo:
        st.setdefault(s.stocktype_id,[]).append(s)
    # Convert to a list of lists; each inner list contains items with
    # the same stocktype
    st=[x for x in list(st.values())]
    # We might want to sort the list at this point... sorting by ascending
    # amount remaining will put the things that are closest to running out
    # near the start - handy!
    remfunc=lambda a:reduce(lambda x,y:x+y,[x.remaining for x in a])
    cmpfunc=lambda a,b:(0,-1)[remfunc(a)<remfunc(b)]
    st.sort(cmpfunc)
    # We want to show name, remaining, items in each line
    # and when a line is selected we want to pop up the list of individual
    # items.
    sl=[]
    f=ui.tableformatter(' l l l ')
    for i in st:
        name=i[0].stocktype.format(maxw=40)
        remaining=reduce(lambda x,y:x+y,[x.remaining for x in i])
        items=len(i)
        unit=i[0].stocktype.unit.name
        sl.append(
            (ui.tableline(
                    f,(name,"%.0f %ss"%(remaining,unit),"(%d item%s)"%(
                            items,("s","")[items==1]))),
             stockdetail,(i,)))
    title="Stock Check" if dept is None else "Stock Check department %d"%dept
    ui.menu(sl,title=title,blurb="Select a stock type and press "
            "Cash/Enter for details on individual items.",
            dismiss_on_select=False,keymap={
            keyboard.K_PRINT: (print_stocklist_menu,(sinfo,title),False)})

@user.permission_required('stock-history','List finished stock')
def stockhistory(dept=None):
    # Build a list of all finished stock items.  Things we want to show:
    log.info("Stock history")
    sq=td.s.query(StockItem).join(StockItem.stocktype).\
        filter(StockItem.finished!=None).\
        order_by(StockItem.id.desc())
    if dept: sq=sq.filter(StockType.dept_id==dept)
    sinfo=sq.all()
    f=ui.tableformatter(' r l l ')
    sl=[(ui.tableline(f,(x.id,x.stocktype.format(),x.remaining_units)),
         stock.stockinfo_popup,(x.id,)) for x in sinfo]
    title=("Stock History" if dept is None
           else "Stock History department %d"%dept)
    ui.menu(sl,title=title,blurb="Select a stock item and press "
            "Cash/Enter for more information.  The number of units remaining "
            "when the stock was finished is shown.",dismiss_on_select=False,
            keymap={
            keyboard.K_PRINT: (printer.print_stocklist,(sinfo,title),False)})

@user.permission_required('update-supplier','Update supplier details')
def updatesupplier():
    log.info("Update supplier")
    delivery.selectsupplier(
        lambda x:delivery.editsupplier(lambda a:None,x),allow_new=False)

class stocklevelcheck(user.permission_checked,ui.dismisspopup):
    permission_required=('stock-level-check','Check stock levels')
    def __init__(self):
        depts=td.s.query(Department).order_by(Department.id).all()
        ui.dismisspopup.__init__(self,10,50,title="Stock level check",
                                 colour=ui.colour_input)
        self.addstr(2,2,'Department:')
        self.deptfield=ui.listfield(2,14,20,depts,
                                    d=lambda x:x.description,
                                    keymap={
                keyboard.K_CLEAR: (self.dismiss,None)})
        self.addstr(3,2,'    Period:')
        self.pfield=ui.editfield(3,14,3,validate=ui.validate_int,keymap={
                keyboard.K_CASH: (self.enter,None)})
        self.addstr(3,18,'weeks')
        self.addstr(5,2,'The period should usually be one-and-a-half')
        self.addstr(6,2,'times the usual time between deliveries.  For')
        self.addstr(7,2,'weekly deliveries use 2; for fortnightly')
        self.addstr(8,2,'deliveries use 3.')
        ui.map_fieldlist([self.deptfield,self.pfield])
        self.deptfield.focus()
    def enter(self):
        if self.pfield=='':
            ui.infopopup(["You must enter a period."],title="Error")
            return
        weeks=int(self.pfield.f)
        dept=(None if self.deptfield.f is None
              else self.deptfield.read())
        if dept: td.s.add(dept)
        self.dismiss()
        q=td.s.query(StockType,func.sum(StockOut.qty)).\
            join(StockItem).\
            join(StockOut).\
            options(lazyload(StockType.department)).\
            options(lazyload(StockType.unit)).\
            options(undefer(StockType.instock)).\
            filter(StockOut.removecode_id=='sold').\
            filter((func.now()-StockOut.time)<"{} weeks".format(weeks)).\
            having(func.sum(StockOut.qty)>0).\
            group_by(StockType).\
            order_by(desc(func.sum(StockOut.qty)-StockType.instock))
        if dept:
            q=q.filter(StockType.dept_id==dept.id)
        r=q.all()
        f=ui.tableformatter(' l r  r  r ')
        lines=[ui.tableline(f,(st.format(),sold,st.instock,sold-st.instock))
               for st,sold in r]
        header=[ui.lrline("Do not order any stock if the 'Buy' amount "
                          "is negative!"),
                ui.emptyline(),
                ui.tableline(f,('Name','Sold','In stock','Buy'))]
        ui.listpopup(lines,header=header,
                     title="Stock level check - %d weeks"%weeks,
                     colour=ui.colour_info,show_cursor=False,
                     dismiss=keyboard.K_CASH)

@user.permission_required(
    'purge-finished-stock',
    "Mark empty stock items on display stocklines as finished")
def purge_finished_stock():
    td.stock_purge()

@user.permission_required(
    'alter-stocktype',
    'Alter an existing stock type to make minor corrections')
def correct_stocktype():
    stocktype.choose_stocktype(
        lambda x:stocktype.choose_stocktype(lambda:None,default=x,mode=2),
        allownew=False)

def maintenance():
    "Pop up the stock maintenance menu."
    menu=[
        (keyboard.K_THREE,"Auto-allocate stock to lines",
         usestock.auto_allocate,None),
        (keyboard.K_FOUR,"Manage stock line associations",
         stocklines.stockline_associations,None),
        (keyboard.K_FIVE,"Update supplier details",updatesupplier,None),
        (keyboard.K_SIX,"Re-price stock",
         stocktype.choose_stocktype,(stocktype.reprice_stocktype,None,1,False)),
        (keyboard.K_SEVEN,"Correct a stock type record",
         correct_stocktype,None),
        (keyboard.K_EIGHT,"Purge finished stock from stock lines",
         purge_finished_stock,None),
        ]
    ui.keymenu(menu,"Stock Maintenance options")

def popup():
    "Pop up the stock management menu."
    log.info("Stock management popup")
    menu=[
        (keyboard.K_ONE,"Deliveries",delivery.deliverymenu,None),
        (keyboard.K_TWO,"Re-fill all stock lines",stocklines.restock_all,None),
        (keyboard.K_THREE,"Re-fill stock lines by location",
         stocklines.restock_location,None),
        (keyboard.K_FOUR,"Finish stock not currently on sale",
         finishstock,None),
        (keyboard.K_FIVE,"Stock check (unfinished stock)",
         department.menu,(stockcheck,"Stock Check",True)),
        (keyboard.K_SIX,"Stock history (finished stock)",
         department.menu,(stockhistory,"Stock History",True)),
        (keyboard.K_SEVEN,"Maintenance submenu",maintenance,None),
        (keyboard.K_EIGHT,"Annotate a stock item",stock.annotate,None),
        (keyboard.K_NINE,"Check stock levels",stocklevelcheck,None),
        ]
    ui.keymenu(menu,"Stock Management options")
