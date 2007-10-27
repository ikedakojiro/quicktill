import ui,stock,td,priceguess,curses.ascii,keyboard

def create_and_edit_delivery(supplier):
    dn=td.delivery_new(supplier)
    delivery(dn)

def deliverylist(func,unchecked_only=False,checked_only=False):
    def d(x):
        return "%s%s%s"%(x[5],' '*(30-len(x[5])-len(x[3])),ui.formatdate(x[3]))
    dl=td.delivery_get(unchecked_only=unchecked_only,checked_only=checked_only)
    m=[(d(x),func,(x[0],)) for x in dl]
    ui.menu(m,title="Delivery List",blurb="Select a delivery and press Cash/Enter.")

class delivery(ui.basicpopup):
    """The delivery window allows a delivery to be edited, printed or
    confirmed.  Prior to confirmation all details of a delivery can be
    changed.  After confirmation the delivery is read-only.  The window
    contains a header area, with supplier name, delivery date and
    document number; a couple of prompts, and a scrollable list of stock
    items.  If the window is not read-only, there is always a blank line
    at the bottom of the list to enable new entries to be made."""
    def __init__(self,dn):
        self.dn=dn
        self.ltop=7
        self.top=0
        self.cursor=None
        self.h=12
        (id,supplier,docnumber,date,checked,supname)=td.delivery_get(number=dn)[0]
        self.dl=td.delivery_items(dn)
        if checked:
            self.readonly=True
            title="Delivery Details - read only"
        else:
            self.readonly=False 
            title="Delivery Details"
            self.dl.append(None) # marks the "new item" entry
        km={keyboard.K_PRINT: (self.printout,None,False),
            keyboard.K_DOWN: (self.cursor_move,(1,),False),
            keyboard.K_UP: (self.cursor_move,(-1,),False),
            keyboard.K_RIGHT: (self.cursor_move,(5,),False),
            keyboard.K_LEFT: (self.cursor_move,(-5,),False),
            }
        if not self.readonly:
            km[keyboard.K_CANCEL]=(self.deleteline,None,False)
            km[keyboard.K_CASH]=(self.edit_line,None,False)
        ui.basicpopup.__init__(self,23,80,title=title,
                               colour=ui.colour_input,keymap=km)
        km={keyboard.K_PRINT: (self.printout,None,False)}
        self.win=self.pan.window()
        self.win.addstr(2,2,"       Supplier:")
        self.win.addstr(3,2,"           Date:")
        self.win.addstr(4,2,"Document number:")
        self.win.addstr(self.ltop-1,1,
                        "StockNo Stock Type........................... "
                        "Unit.... Cost.. Sale  BestBefore")
        self.win.addstr(20,50,"Press Print for a hard copy.")
        self.supfield=ui.popupfield(self.win,2,19,59,selectsupplier,
                                    self.supplier_value,keymap=km,
                                    f=supplier,readonly=self.readonly)
        self.datefield=ui.datefield(self.win,3,19,keymap=km,
                                    f=date,readonly=self.readonly)
        self.docnumfield=ui.editfield(self.win,4,19,40,keymap=km,
                                      f=docnumber,readonly=self.readonly)
        fl=[self.supfield,self.datefield,self.docnumfield]
        if not self.readonly:
            self.deletefield=ui.buttonfield(self.win,21,2,24,
                                            "Delete this delivery",
                                            keymap=km)
            self.deletefield.keymap[keyboard.K_CASH]=(self.confirmdelete,None,False)
            fl.append(self.deletefield)
            self.field_after_list=self.deletefield
            self.confirmfield=ui.buttonfield(self.win,21,28,31,
                                             "Confirm details are correct",
                                             keymap=km)
            self.confirmfield.keymap[keyboard.K_CASH]=(self.confirmcheck,None,False)
            fl.append(self.confirmfield)
        self.savefield=ui.buttonfield(self.win,21,61,17,
                                      ("Save and exit","Exit")[self.readonly],
                                      keymap=km)
        self.savefield.keymap[keyboard.K_CASH]=(self.finish,None,False)
        if self.readonly:
            self.field_after_list=self.savefield
        fl.append(self.savefield)
        ui.map_fieldlist(fl)
        # Modify the key bindings for the "docnum" field
        self.docnumfield.keymap[keyboard.K_DOWN]=(self.docnumnavdown,None,True)
        self.docnumfield.keymap[keyboard.K_CASH]=(self.docnumnavdown,None,True)
        self.docnumfield.keymap[curses.ascii.TAB]=(self.docnumnavdown,None,True)
        # Modify the key binding for the first field in the footer section
        if self.readonly:
            self.savefield.keymap[keyboard.K_UP]=(self.footernavup,None,True)
        else:
            self.deletefield.keymap[keyboard.K_UP]=(self.footernavup,None,True)
        self.drawdl()
        self.datefield.focus()
    def reallydeleteline(self):
        td.stock_delete(self.dl[self.cursor])
        self.dl=td.delivery_items(self.dn)+[None]
        if len(self.dl)==0 or self.cursor>=len(self.dl):
            self.cursor=0
        self.drawdl()
    def deleteline(self):
        if self.cursor is not None and self.dl[self.cursor] is not None:
            ui.infopopup(["Press Cash/Enter to confirm deletion of stock number %d. "
                          "Note that once it's deleted you can't create a new stock "
                          "item with the same number; new stock items always get "
                          "fresh numbers."%self.dl[self.cursor]],title="Confirm Delete",
                         keymap={keyboard.K_CASH:(self.reallydeleteline,None,True)})
    def pack_fields(self):
        # Check that there's still a supplier selected
        if self.supfield.f is None:
            ui.infopopup(["Select a supplier before continuing!"],title="Error")
            return None
        # Check that the date field is valid
        d=self.datefield.read()
        if d is None:
            ui.infopopup(["Check that the delivery date is correct before "
                          "continuing!"],title="Error")
            return None
        return (self.supfield.f,self.datefield.read(),self.docnumfield.f)
    def finish(self):
        pf=self.pack_fields()
        if pf is not None:
            td.delivery_update(self.dn,*pf)
            self.dismiss()
    def printout(self):
        printer.print_delivery(self.dn)
    def footernavup(self):
        # Called when "up" is pressed on the first button in the
        # footer.  If dl is not empty, moves cursor to last entry in
        # dl; otherwise moves to document number field
        if len(self.dl)==0:
            self.docnum.focus()
        else:
            self.setcursor(len(self.dl)-1)
    def docnumnavdown(self):
        # Called when "down" or "Enter" is pressed on the docnum field; if dl is
        # not empty, moves cursor to first entry in dl; otherwise moves to "new"
        # field.
        if len(self.dl)>0: self.setcursor(0)
        else:
            # Must be readonly...
            self.savefield.focus()
    def reallyconfirm(self):
        # Set the Confirm flag
        self.finish()
        td.delivery_check(self.dn)
    def confirmcheck(self):
        if self.pack_fields() is None: return
        # The confirm button was pressed; set the flag
        ui.infopopup(["When you confirm a delivery you are asserting that "
                      "you have received and checked every item listed as part "
                      "of the delivery.  Once the delivery is confirmed, you "
                      "can't go back and change any of the details.  Press "
                      "Cash/Enter to confirm this delivery now, or Clear to "
                      "continue editing it."],title="Confirm Details",
                     keymap={keyboard.K_CASH:(self.reallyconfirm,None,True)})
    def drawline(self,line):
        if line<self.top or line>=len(self.dl): return
        y=line-self.top+self.ltop
        if y>(self.h+self.ltop): return
        if self.dl[line] is None:
            s=" New item "
        else:
            sd=td.stock_info(self.dl[line])
            typestr=stock.format_stock(sd,maxw=37)
            s="%7d %-37s %-8s %-6.2f %-5.2f %-10s"%(
                self.dl[line],typestr,sd['stockunit'],sd['costprice'],
                sd['saleprice'],ui.formatdate(sd['bestbefore']))
        attr=(0,curses.A_REVERSE)[line==self.cursor]
        self.win.addstr(y,1,s,attr)
    def drawdl(self):
        for i in range(self.ltop,self.ltop+self.h+1):
            self.win.addstr(i,1,' '*78)
        for i in range(0,len(self.dl)):
            self.drawline(i)
    def setcursor(self,line):
        oc=self.cursor
        self.cursor=None
        if oc is not None:
            self.drawline(oc)
        self.win.addstr(20,2,' '*40)
        if line>len(self.dl): line=len(self.dl)-1
        if line<0:
            self.docnumfield.focus()
        elif line>=len(self.dl):
            self.field_after_list.focus()
        else:
            self.cursor=line
            if self.cursor<self.top:
                self.top=self.cursor-(self.h/2*3)
                if self.top<0: self.top=0
                self.drawdl()
            if (self.cursor-self.top)>self.h:
                self.top=self.cursor-(self.h/3)
                if self.top<0: self.top=0
                self.drawdl()
        if self.cursor is not None:
            if not self.readonly and self.dl[self.cursor] is not None:
                self.win.addstr(20,2,"Press Cancel to delete this stock item.")
            self.drawline(self.cursor)
    def cursor_move(self,n):
        if self.cursor is not None:
            self.setcursor(self.cursor+n)
    def line_edited(self,sn):
        self.dl=td.delivery_items(self.dn)+[None]
        self.drawdl()
        self.setcursor(self.cursor+1)
    def edit_line(self):
        stockline(self.line_edited,self.dn,self.dl[self.cursor])
    def reallydelete(self):
        td.delivery_delete(self.dn)
        self.dismiss()
    def confirmdelete(self):
        ui.infopopup(["Do you want to delete the entire delivery and all the stock "
                      "items that have been entered for it?  Press Cancel to delete "
                      "or Clear to go back."],title="Confirm Delete",
                     keymap={keyboard.K_CANCEL:(self.reallydelete,None,True)})
    def supplier_value(self,sup):
        (name,tel,email)=td.supplier_fetch(sup)
        return name

class stockline(ui.basicpopup):
    def __init__(self,func,dn,sn=None):
        self.func=func
        self.sn=sn
        self.dn=dn
        ui.basicpopup.__init__(self,12,78,title="Stock Item",
                               cleartext="Press Clear to exit, forgetting "
                               "all changes",colour=ui.colour_line)
        win=self.pan.window()
        self.units=[]
        if sn is None:
            win.addstr(2,2,"Stock number not yet assigned")
        else:
            win.addstr(2,2,"        Stock number: %d"%sn)
        win.addstr(3,2,"          Stock type:")
        win.addstr(4,2,"                Unit:")
        win.addstr(5,2," Cost price (ex VAT): �")
        win.addstr(6,2,"Sale price (inc VAT): �")
        win.addstr(7,2,"         Best before:")
        km={keyboard.K_CLEAR: (self.dismiss,None,True)}
        self.typefield=ui.popupfield(win,3,24,52,stock.stocktype,
                                     stock.format_stocktype,keymap=km)
        self.typefield.sethook=self.updateunitfield
        self.unitfield=ui.listfield(win,4,24,20,None,keymap=km)
        self.costfield=ui.editfield(win,5,25,6,keymap=km,
                                    validate=ui.validate_float)
        self.costfield.sethook=self.guesssaleprice
        self.salefield=ui.editfield(win,6,25,6,keymap=km,
                                    validate=ui.validate_float)
        self.bestbeforefield=ui.datefield(win,7,24,keymap=km)
        self.acceptbutton=ui.buttonfield(win,9,28,21,"Accept values",
                                         keymap=km)
        self.acceptbutton.keymap[keyboard.K_CASH]=(self.accept,None,False)
        fl=[self.typefield,self.unitfield,self.costfield,self.salefield,
            self.bestbeforefield,self.acceptbutton]
        ui.map_fieldlist(fl)
        if sn is not None:
            self.fill_fields(sn)
            if self.bestbeforefield.f=="":
                self.bestbeforefield.focus()
            else:
                self.acceptbutton.focus()
        else:
            self.typefield.focus()
    def fill_fields(self,sn):
        sd=td.stock_info(sn)
        self.typefield.set(sd['stocktype'])
        self.updateunitfield(default=sd['stockunit'])
        self.costfield.set("%0.2f"%sd['costprice'])
        self.salefield.set("%0.2f"%sd['saleprice'])
        self.bestbeforefield.set(sd['bestbefore'])
    def pack_fields(self):
        if self.typefield.f is None: return None
        if self.unitfield.f is None: return None
        if len(self.costfield.f)==0: return None
        if len(self.salefield.f)==0: return None
        return (self.typefield.f,self.units[self.unitfield.f],
                float(self.costfield.f),float(self.salefield.f),
                self.bestbeforefield.read())
    def accept(self):
        pf=self.pack_fields()
        if pf is None:
            ui.infopopup(["You have not filled in all the fields.  "
                          "The only optional field is 'Best Before'."],
                         title="Error")
            return
        self.dismiss()
        if self.sn is None:
            self.sn=td.stock_receive(self.dn,*pf)
        else:
            td.stock_update(self.sn,*pf)
        self.func(self.sn)
    def updateunitfield(self,default=None):
        # If the unit field contains a value which is not valid for
        # the unittype of the selected stock type, rebuild the list of
        # stockunits
        if self.typefield.f==None:
            self.unitfield.l=[]
            self.unitfield.set(None)
            return
        (dept,manufacturer,name,shortname,abv,unit)=td.stocktype_info(
            self.typefield.f)
        ul=td.stockunits_list(unit)
        if default is not None:
            oldunit=default
        elif self.unitfield.f is not None:
            oldunit=self.units[self.unitfield.f]
        else: oldunit=None
        self.units=[x[0] for x in ul]
        if oldunit in self.units:
            newunit=self.units.index(oldunit)
        else: newunit=0
        self.unitfield.l=self.units
        self.unitfield.d=dict([(x[0],x[1]) for x in ul])
        self.unitfield.set(newunit)
    def guesssaleprice(self):
        # Called when the Cost field has been filled in
        if self.typefield.f is None or self.unitfield.f is None: return
        (dept,manufacturer,name,shortname,abv,unit)=td.stocktype_info(self.typefield.f)
        (uname,size)=td.stockunits_info(self.units[self.unitfield.f])
        if len(self.costfield.f)>0:
            wholeprice=float(self.costfield.f)
            g=priceguess.guess(dept,(wholeprice/size),abv)
            if g is not None and self.salefield.f=="":
                self.salefield.set("%0.2f"%g)

def selectsupplier(func,default=0,allow_new=True):
    sl=td.supplier_list()
    if allow_new: m=[("New supplier",editsupplier,(func,))]
    else: m=[]
    m=m+[(x[1],func,(x[0],)) for x in sl]
    ui.menu(m,blurb="Select a supplier from the list and press Cash/Enter.",
            title="Select Supplier",default=default)

class editsupplier(ui.basicpopup):
    def __init__(self,func,sn=None):
        self.func=func
        self.sn=sn
        if sn is not None: (name,tel,email)=td.supplier_fetch(sn)
        else: (name,tel,email)=("","","")
        ui.basicpopup.__init__(self,10,70,title="Supplier Details",
                               colour=ui.colour_input,cleartext=
                               "Press Clear to go back")
        win=self.pan.window()
        win.addstr(2,2,"Please enter the supplier's details. You may ")
        win.addstr(3,2,"leave the telephone and email fields blank if you wish.")
        win.addstr(5,2,"     Name:")
        win.addstr(6,2,"Telephone:")
        win.addstr(7,2,"    Email:")
        km={keyboard.K_CLEAR: (self.dismiss,None,True)}
        self.namefield=ui.editfield(win,5,13,55,flen=60,keymap=km,f=name)
        self.telfield=ui.editfield(win,6,13,20,keymap=km,f=tel)
        self.emailfield=ui.editfield(win,7,13,55,flen=60,keymap=km,f=email)
        fl=[self.namefield,self.telfield,self.emailfield]
        ui.map_fieldlist(fl)
        self.emailfield.keymap[keyboard.K_CASH]=(
            (self.confirmed,self.confirmwin)[sn is None],None,True)
        self.namefield.focus()
    def confirmwin(self):
        # Called when Cash/Enter is pressed on the last field, for new suppliers only
        self.dismiss()
        # popup stuff
        ui.infopopup(["Press Cash/Enter to confirm new supplier details:",
                      "Name: %s"%self.namefield.f,
                      "Telephone: %s"%self.telfield.f,
                      "Email: %s"%self.emailfield.f],title="Confirm New Supplier Details",
                     colour=ui.colour_input,keymap={
            keyboard.K_CASH: (self.confirmed,None,True)})
    def confirmed(self):
        if self.sn is None:
            self.sn=td.supplier_new(self.namefield.f,self.telfield.f,self.emailfield.f)
        else:
            self.dismiss()
            td.supplier_update(self.sn,self.namefield.f,self.telfield.f,self.emailfield.f)
        self.func(self.sn)
