import time
from . import ui,event,td,keyboard,usestock,stocklines

class page(ui.basicpage):
    def __init__(self,hotkeys,locations=None):
        ui.basicpage.__init__(self)
        self.mainloopnexttime=0 # XXX needed when being created dynamically
        # - sort out the event loop code sometime so it doesn't need this!
        self.display=0
        self.alarm(need_new_session=False)
        self.hotkeys=hotkeys
        self.locations=locations if locations else ['Bar']
        event.eventlist.append(self)
        self.updateheader()
    def pagename(self):
        return "Stock Control"
    def drawlines(self):
        sl=td.stockline_summary(td.s,self.locations)
        y=1
        self.addstr(0,0,"Line")
        self.addstr(0,10,"StockID")
        self.addstr(0,18,"Stock")
        self.addstr(0,64,"Used")
        self.addstr(0,70,"Remaining")
        for line in sl:
            self.addstr(y,0,line.name)
            if len(line.stockonsale)>0:
                # We are only showing stock lines with null capacity.
                # There should be no more than one stock item on sale
                # at once.  Here we explicitly use the first one.
                sos=line.stockonsale[0]
                self.addstr(y,10,"%d"%sos.id)
                self.addstr(y,18,sos.stocktype.format(45))
                self.addstr(y,64,"%0.1f"%sos.used)
                self.addstr(y,73,"%0.1f"%sos.remaining)
            y=y+1
            if y>=(self.h-3): break
    def drawstillage(self):
        sl=td.stillage_summary(td.s)
        y=1
        self.addstr(0,0,"Loc")
        self.addstr(0,5,"StockID")
        self.addstr(0,13,"Name")
        self.addstr(0,70,"Line")
        for a in sl:
            self.addstr(y,0,a.text[:5])
            self.addstr(y,5,str(a.stockid))
            self.addstr(y,13,a.stockitem.stocktype.format(56))
            if a.stockitem.stockline:
                self.addstr(y,70,a.stockitem.stockline.name[:9])
            y=y+1
            if y>=(self.h-3): break
    def redraw(self):
        win=self.win
        win.erase()
        self.addstr(self.h-1,0,"Ctrl+X = Clear; Ctrl+Y = Cancel")
        self.addstr(self.h-2,0,"Press S for stock management.  "
                   "Press U to use stock.  Press R to record waste.")
        self.addstr(self.h-3,0,"Press Enter to refresh display.  "
                   "Press A to add a stock annotation.")
        if self.display==0:
            self.drawlines()
        elif self.display==1:
            self.drawstillage()
    def alarm(self,need_new_session=True):
        self.nexttime=time.time()+60.0
        self.display=self.display+1
        if self.display>1: self.display=0
        # There won't be a database session set up when we're called
        # by the timer expiring.
        if need_new_session: td.start_session()
        self.redraw()
        if need_new_session: td.end_session()
    def keypress(self,k):
        if k in self.hotkeys: return self.hotkeys[k]()
        elif k==keyboard.K_CASH:
            self.alarm(need_new_session=False)
        elif k==ord('u') or k==ord('U'):
            stocklines.selectline(usestock.line_chosen,
                                  title="Use Stock",
                                  blurb="Select a stock line",exccap=True)
        else:
            ui.beep()
    def deselect(self):
        # Ensure that we're not still hanging around when we are invisible
        ui.basicpage.deselect(self)
        del event.eventlist[event.eventlist.index(self)]
        self.dismiss()
