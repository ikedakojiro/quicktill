"""This module is referred to by all the other modules that make up
the till software for global till configuration.  It is expected that
the local till configuration file will import this module and replace
most of the entries here.

"""

from .models import penny

configversion="tillconfig.py"

pubname="Test Pub Name"
pubnumber="07715 422132"
pubaddr=("31337 Beer Street","Burton","ZZ9 9AA")

# Test multi-character currency name... monopoly money!
currency="MPL"

hotkeys={}

all_payment_methods=[]
payment_methods=[]

def pricepolicy(si,qty):
    """How much does qty of stock item sd cost? qty is a Decimal,
    eg. 1.0 or 0.5, and si is a StockItem

    """
    return qty*si.stocktype.saleprice

def fc(a):
    """Format currency, using the configured currency symbol."""
    if a is None: return "None"
    return "%s%s"%(currency,a.quantize(penny))

def priceguess(stocktype,stockunit,cost):
    """
    Guess a suitable selling price for a new stock item.  Return a
    price, or None if there is no suitable guess available.  'cost' is
    the cost price _per stockunit_, eg. per cask for beer.

    """
    return None

# A function that takes (models.Department object,price) and returns
# either None (if there is no problem), or a string or list of strings
# to display to the user (if there is a problem).
#
# This is a deprecated configuration setting; deptkeycheck should now
# be specified as the "checkfunction" argument to keyboard.deptkey()
deptkeycheck=None

# Do we print check digits on stock labels?
checkdigit_print=False
# Do we ask the user to input check digits when using stock?
checkdigit_on_usestock=False

# Hook that is called whenever an item of stock is put on sale, with
# a StockItem and StockLine as the arguments
def usestock_hook(stock,line):
    pass

database=None

firstpage=None

# Called by ui code whenever a usertoken is processed by the default
# page's hotkey handler
def usertoken_handler(t):
    pass
usertoken_listen=None

# A function to turn off the screensaver if the screen has gone blank
def unblank_screen():
    pass
