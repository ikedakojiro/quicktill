import curses.ascii
from . import ui,stock,td,keyboard,printer,tillconfig,stocklines
from decimal import Decimal
from .models import Delivery,Supplier,StockUnit,StockItem,desc
import datetime

def deliverymenu():
    """Display a list of deliveries and call the edit function.

    """
    def d(x):
        return (str(x.id),x.supplier.name,str(x.date),
                ("not confirmed","")[x.checked])
    session=td.sm()
    dl=session.query(Delivery).\
        order_by(Delivery.checked).\
        order_by(desc(Delivery.date)).\
        order_by(desc(Delivery.id)).\
        all()
    session.close()
    lines=ui.table([d(x) for x in dl]).format(' r l l l ')
    m=[(x,delivery,(y.id,)) for x,y in zip(lines,dl)]
    m.insert(0,("Record new delivery",delivery,None))
    ui.menu(m,title="Delivery List",
            blurb="Select a delivery and press Cash/Enter.")

class deliveryline(ui.line):
    def __init__(self,stockitem,session):
        ui.line.__init__(self)
        self.stockid=stockitem.id
        self.update(session)
    def update(self,session):
        s=session.query(StockItem).get(self.stockid)
        try:
            coststr="%-6.2f"%s.costprice
        except:
            coststr="????? "
        self.text="%7d %-37s %-8s %s %-5.2f %-10s"%(
            s.id,s.stocktype.format(maxw=37),s.stockunit.id,
            coststr,s.saleprice,ui.formatdate(s.bestbefore))

class delivery(ui.basicpopup):
    """The delivery window allows a delivery to be edited, printed or
    confirmed.  Prior to confirmation all details of a delivery can be
    changed.  After confirmation the delivery is read-only.  The window
    contains a header area, with supplier name, delivery date and
    document number; a couple of prompts, and a scrollable list of stock
    items.  If the window is not read-only, there is always a blank line
    at the bottom of the list to enable new entries to be made.

    If no delivery ID is passed, a new delivery will be created once a
    supplier has been chosen.

    """
    def __init__(self,dn=None):
        (mh,mw)=ui.stdwin.getmaxyx()
        if mw<80 or mh<14:
            ui.infopopup(["Error: the screen is too small to display "
                          "the delivery dialog box.  It must be at least "
                          "80x14 characters."],
                         title="Screen width problem")
            return
        session=td.sm()
        if dn:
            d=session.query(Delivery).get(dn)
        else: d=None
        if d:
            self.dl=[deliveryline(x,session) for x in d.items]
            self.dn=d.id
        else:
            self.dl=[]
            self.dn=None
        if d and d.checked:
            title="Delivery Details - read only (already confirmed)"
            cleartext="Press Clear to go back"
            skm={keyboard.K_CASH: (self.view_line,None)}
        else:
            title="Delivery Details"
            cleartext=None
            skm={keyboard.K_CASH: (self.edit_line,None),
                 keyboard.K_CANCEL: (self.deleteline,None),
                 keyboard.K_QUANTITY: (self.duplicate_item,None)}
        # The window can be as tall as the screen; we expand the scrollable
        # field to fit.  The scrollable field must be at least three lines
        # high!
        ui.basicpopup.__init__(self,mh-1,80,title=title,cleartext=cleartext,
                               colour=ui.colour_input)
        self.addstr(2,2,"       Supplier:")
        self.addstr(3,2,"           Date:")
        self.addstr(4,2,"Document number:")
        self.addstr(6,1,"StockNo Stock Type........................... "
                        "Unit.... Cost.. Sale  BestBefore")
        self.supfield=ui.popupfield(2,19,59,selectsupplier,lambda x:unicode(x),
                                    f=d.supplier if d else None,
                                    readonly=d.checked if d else False)
        # If there is not yet an underlying Delivery object, the window
        # can be dismissed by pressing Clear on the supplier field
        if self.dn is None:
            self.supfield.keymap[keyboard.K_CLEAR]=(self.dismiss,None)
        self.datefield=ui.datefield(
            3,19,f=d.date if d else datetime.date.today(),
            readonly=d.checked if d else False)
        self.docnumfield=ui.editfield(4,19,40,f=d.docnumber if d else "",
                                      readonly=d.checked if d else False)
        self.entryprompt=None if d and d.checked else ui.line(
            " [ New item ]")
        self.s=ui.scrollable(
            7,1,78,mh-9 if d and d.checked else mh-11,self.dl,
            lastline=self.entryprompt,keymap=skm)
        session.close()
        if d and d.checked:
            self.s.focus()
        else:
            self.deletefield=ui.buttonfield(
                mh-3,2,24,"Delete this delivery",keymap={
                    keyboard.K_CASH: (self.confirmdelete,None)})
            self.confirmfield=ui.buttonfield(
                mh-3,28,31,"Confirm details are correct",keymap={
                    keyboard.K_CASH: (self.confirmcheck,None)})
            self.savefield=ui.buttonfield(
                mh-3,61,17,"Save and exit",keymap={
                    keyboard.K_CASH: (self.finish,None)})
            ui.map_fieldlist(
                [self.supfield,self.datefield,self.docnumfield,self.s,
                 self.deletefield,self.confirmfield,self.savefield])
            self.supfield.focus()
            if not self.dn: self.supfield.popup()
    def reallydeleteline(self):
        session=td.sm()
        stockitem=session.query(StockItem).get(self.dl[self.s.cursor].stockid)
        session.delete(stockitem)
        session.commit()
        session.close()
        del self.dl[self.s.cursor]
        self.s.drawdl()
    def deleteline(self):
        if not self.s.cursor_on_lastline():
            ui.infopopup(
                ["Press Cash/Enter to confirm deletion of stock "
                 "number %d.  Note that once it's deleted you can't "
                 "create a new stock item with the same number; new "
                 "stock items always get fresh numbers."%(
                        self.dl[self.s.cursor].stockid)],
                title="Confirm Delete",
                keymap={keyboard.K_CASH:(self.reallydeleteline,None,True)})
    def pack_fields(self,model,session=None):
        """Update the supplied model with the field contents.  Return
        True if ok, otherwise return None.

        """
        if self.supfield.f is None:
            ui.infopopup(["Select a supplier before continuing!"],title="Error")
            return
        if session: self.supfield.f=session.merge(self.supfield.f)
        model.supplier=self.supfield.f
        d=self.datefield.read()
        if d is None:
            ui.infopopup(["Check that the delivery date is correct before "
                          "continuing!"],title="Error")
            return
        model.date=d
        if self.docnumfield.f=="":
            ui.infopopup(["Enter a document number before continuing!"],
                         title="Error")
            return
        model.docnumber=self.docnumfield.f
        return True
    def finish(self):
        session=td.sm()
        d=session.query(Delivery).get(self.dn)
        if self.pack_fields(d,session):
            self.dismiss()
        session.commit()
        session.close()
    def printout(self):
        if self.dn is None: return
        session=td.sm()
        d=session.query(Delivery).get(self.dn)
        try:
            if not self.pack_fields(d,session): return
        finally:
            session.close()
        if printer.labeldriver is not None:
            menu=[
                (keyboard.K_ONE,"Print list",
                 printer.print_delivery,(d.id,)),
                (keyboard.K_TWO,"Print sticky labels",
                 printer.label_print_delivery,(d.id,)),
                ]
            ui.keymenu(menu,"Delivery print options",colour=ui.colour_confirm)
        else:
            printer.print_delivery(d.id)
    def reallyconfirm(self):
        session=td.sm()
        d=session.query(Delivery).get(self.dn)
        self.pack_fields(d,session)
        d.checked=True
        session.commit()
        session.close()
        self.dismiss()
        stocklines.auto_allocate(deliveryid=self.dn,confirm=False)
    def confirmcheck(self):
        if not self.pack_fields(Delivery()): return
        # The confirm button was pressed; set the flag
        ui.infopopup(["When you confirm a delivery you are asserting that "
                      "you have received and checked every item listed as part "
                      "of the delivery.  Once the delivery is confirmed, you "
                      "can't go back and change any of the details.  Press "
                      "Cash/Enter to confirm this delivery now, or Clear to "
                      "continue editing it."],title="Confirm Details",
                     keymap={keyboard.K_CASH:(self.reallyconfirm,None,True)})
    def line_edited(self,stockitem):
        # Only called when a line has been edited; not called for new
        # lines or deletions
        session=td.sm()
        session.add(stockitem)
        self.dl[self.s.cursor].stockid=stockitem.id
        self.dl[self.s.cursor].update(session)
        self.s.cursor_down()
        session.commit()
        session.close()
    def newline(self,stockitem):
        # The stockitem will not have been persisted
        session=td.sm()
        stockitem.deliveryid=self.dn
        session.add(stockitem)
        session.commit()
        self.dl.append(deliveryline(stockitem,session))
        self.s.cursor_down()
        session.close()
    def edit_line(self):
        # If there is not yet an underlying Delivery object, create one
        if self.dn is None:
            session=td.sm()
            d=Delivery()
            if self.pack_fields(d):
                session.add(d)
                session.commit()
            else:
                session.close()
                return
            self.dn=d.id
            del self.supfield.keymap[keyboard.K_CLEAR]
            session.close()
        # If it's the "lastline" then we create a new stock item
        if self.s.cursor_on_lastline():
            stockline(self.newline)
        else:
            stockline(self.line_edited,self.dl[self.s.cursor].stockid)
    def view_line(self):
        # In read-only mode there is no "lastline"
        stock.stockinfo_popup(self.dl[self.s.cursor].stockid)
    def duplicate_item(self):
        ln=self.dl[len(self.dl)-1 if self.s.cursor_on_lastline()
                   else self.s.cursor].stockid
        session=td.sm()
        existing=session.query(StockItem).get(ln)
        # We deliberately do not copy the best-before date, because it
        # might be different on the new item.
        new=StockItem(delivery=existing.delivery,stocktype=existing.stocktype,
                      stockunit=existing.stockunit,costprice=existing.costprice,
                      saleprice=existing.saleprice)
        session.add(new)
        session.flush()
        self.dl.append(deliveryline(new,session))
        self.s.cursor_down()
        session.commit()
        session.close()
    def reallydelete(self):
        if self.dn is None:
            self.dismiss()
            return
        session=td.sm()
        d=session.query(Delivery).get(self.dn)
        for i in d.items:
            session.delete(i)
        session.delete(d)
        session.commit()
        session.close()
        self.dismiss()
    def confirmdelete(self):
        ui.infopopup(["Do you want to delete the entire delivery and all "
                      "the stock items that have been entered for it?  "
                      "Press Cancel to delete or Clear to go back."],
                     title="Confirm Delete",
                     keymap={keyboard.K_CANCEL:(self.reallydelete,None,True)})
    def keypress(self,k):
        if k==keyboard.K_PRINT:
            self.printout()
        elif k==keyboard.K_CLEAR:
            self.dismiss()

class stockline(ui.basicpopup):
    def __init__(self,func,stockid=None):
        # We call func with a StockItem model as argument.  We do not
        # persist the model first.
        self.func=func
        self.stockid=stockid
        cleartext=(
            "Press Clear to exit, forgetting all changes" if stockid else
            "Press Clear to exit without creating a new stock item")
        ui.basicpopup.__init__(self,12,78,title="Stock Item",
                               cleartext=cleartext,colour=ui.colour_line)
        if stockid is None:
            self.addstr(2,2,"Stock number not yet assigned")
        else:
            self.addstr(2,2,"        Stock number: %d"%stockid)
        self.addstr(3,2,"          Stock type:")
        self.addstr(4,2,"                Unit:")
        self.addstr(5,2," Cost price (ex VAT): %s"%tillconfig.currency)
        self.addstr(6,2,"Sale price (inc VAT): %s"%tillconfig.currency)
        self.addstr(7,2,"         Best before:")
        self.typefield=ui.popupfield(
            3,24,52,stock.stocktype,lambda si:si.format(),
            keymap={keyboard.K_CLEAR: (self.dismiss,None)})
        self.unitfield=ui.listfield(4,24,20,[])
        self.costfield=ui.editfield(5,24+len(tillconfig.currency),6,
                                    validate=ui.validate_float)
        self.costfield.sethook=self.guesssaleprice
        self.salefield=ui.editfield(6,24+len(tillconfig.currency),6,
                                    validate=ui.validate_float)
        self.bestbeforefield=ui.datefield(7,24)
        self.acceptbutton=ui.buttonfield(9,28,21,"Accept values",keymap={
                keyboard.K_CASH: (self.accept,None)})
        ui.map_fieldlist(
            [self.typefield,self.unitfield,self.costfield,self.salefield,
             self.bestbeforefield,self.acceptbutton])
        if stockid is not None:
            session=td.sm()
            stockitem=session.query(StockItem).get(stockid)
            self.typefield.set(stockitem.stocktype)
            self.costfield.set(stockitem.costprice)
            self.salefield.set(stockitem.saleprice)
            self.bestbeforefield.set(stockitem.bestbefore)
            session.close()
            self.updateunitfield(default=stockitem.stockunit)
            if self.bestbeforefield.f=="":
                self.bestbeforefield.focus()
            else:
                self.acceptbutton.focus()
        else:
            self.typefield.focus()
        # We can't set this earlier, otherwise we will have nested sessions
        # when typefield.set calls updateunitfield
        self.typefield.sethook=self.updateunitfield
    def check_fields(self):
        if self.typefield.f is None: return None
        if self.unitfield.f is None: return None
        if len(self.salefield.f)==0: return None
        return True
    def accept(self):
        if self.check_fields() is None:
            ui.infopopup(["You have not filled in all the fields.  "
                          "The only optional fields are 'Best Before' "
                          "and 'Cost Price'."],
                         title="Error")
            return
        self.dismiss()
        if len(self.costfield.f)==0:
            cost=None
        else:
            cost=float(self.costfield.f)
        session=td.sm()
        stocktype=session.merge(self.typefield.f)
        stockunit=session.merge(self.unitfield.read())
        if self.stockid:
            stockitem=session.query(StockItem).get(self.stockid)
        else:
            stockitem=StockItem()
        stockitem.stocktype=stocktype
        stockitem.stockunit=stockunit
        stockitem.costprice=cost
        stockitem.saleprice=Decimal(self.salefield.f)
        stockitem.bestbefore=self.bestbeforefield.read()
        session.close()
        # Changes to the model will be persisted by the callee
        self.func(stockitem)
    def updateunitfield(self,default=None):
        # If the unit field contains a value which is not valid for
        # the unittype of the selected stock type, rebuild the list of
        # stockunits
        if self.typefield.f==None:
            self.unitfield.l=[]
            self.unitfield.set(None)
            return
        session=td.sm()
        u=self.unitfield.read()
        if u: session.add(u)
        session.add(self.typefield.f)
        ul=session.query(StockUnit).\
            filter(StockUnit.unit==self.typefield.f.unit).\
            all()
        if default is not None:
            oldunit=default
        elif self.unitfield.f is not None:
            oldunit=self.unitfield.read()
        else: oldunit=None
        if oldunit in ul: newunit=ul.index(oldunit)
        else: newunit=0
        self.unitfield.l=ul
        self.unitfield.set(newunit)
        session.close()
    def guesssaleprice(self):
        # Called when the Cost field has been filled in
        if self.typefield.f is None or self.unitfield.f is None: return
        if len(self.costfield.f)>0 and self.salefield.f=="":
            wholeprice=Decimal(self.costfield.f)
            g=tillconfig.priceguess(
                self.typefield.f.dept_id,(wholeprice/self.unitfield.read().size),
                self.typefield.f.abv)
            if g is not None:
                self.salefield.set("%0.2f"%g)
    def keypress(self,k):
        # If the user starts typing into the stocktype field, be nice
        # to them and pop up the stock type entry dialog.  Then
        # synthesise the keypress again to enter it into the
        # manufacturer field.
        if (ui.focus==self.typefield and self.typefield.f is None
            and curses.ascii.isprint(k)):
            self.typefield.popup() # Grabs the focus
            ui.handle_keyboard_input(k)
        else:
            ui.basicpopup.keypress(self,k)

def selectsupplier(func,default=None,allow_new=True):
    """Choose a supplier; return the appropriate Supplier model,
    detached, by calling func with it as the only argument.

    """
    session=td.sm()
    sl=session.query(Supplier).order_by(Supplier.id).all()
    session.close()
    if allow_new: m=[("New supplier",editsupplier,(func,))]
    else: m=[]
    m=m+[(x.name,func,(x,)) for x in sl]
    # XXX Deal with default processing here
    ui.menu(m,blurb="Select a supplier from the list and press Cash/Enter.",
            title="Select Supplier")

class editsupplier(ui.basicpopup):
    def __init__(self,func,supplier=None):
        self.func=func
        self.sn=supplier.id if supplier else None
        ui.basicpopup.__init__(self,10,70,title="Supplier Details",
                               colour=ui.colour_input,cleartext=
                               "Press Clear to go back")
        self.addstr(2,2,"Please enter the supplier's details. You may ")
        self.addstr(3,2,"leave the telephone and email fields blank if you wish.")
        self.addstr(5,2,"     Name:")
        self.addstr(6,2,"Telephone:")
        self.addstr(7,2,"    Email:")
        self.namefield=ui.editfield(
            5,13,55,flen=60,keymap={
                keyboard.K_CLEAR: (self.dismiss,None)},
            f=supplier.name if supplier else "")
        self.telfield=ui.editfield(
            6,13,20,f=supplier.tel if supplier else "")
        self.emailfield=ui.editfield(
            7,13,55,flen=60,f=supplier.email if supplier else "",
            keymap={
                keyboard.K_CASH:(self.confirmwin if supplier is None
                                 else self.confirmed,None)})
        ui.map_fieldlist([self.namefield,self.telfield,self.emailfield])
        self.namefield.focus()
    def confirmwin(self):
        # Called when Cash/Enter is pressed on the last field, for new
        # suppliers only
        self.dismiss()
        ui.infopopup(["Press Cash/Enter to confirm new supplier details:",
                      "Name: %s"%self.namefield.f,
                      "Telephone: %s"%self.telfield.f,
                      "Email: %s"%self.emailfield.f],
                     title="Confirm New Supplier Details",
                     colour=ui.colour_input,keymap={
            keyboard.K_CASH: (self.confirmed,None,True)})
    def confirmed(self):
        session=td.sm()
        if self.sn:
            supplier=session.query(Supplier).get(sn)
        else:
            supplier=Supplier()
        supplier.name=self.namefield.f
        supplier.tel=self.telfield.f
        supplier.email=self.emailfield.f
        if self.sn is not None: self.dismiss()
        session.add(supplier)
        session.commit()
        # Refresh it here to keep it accessible even if expire_on_commit=True
        session.refresh(supplier)
        session.close()
        self.func(supplier)
