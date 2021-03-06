import logging
log = logging.getLogger(__name__)
from . import payment, ui, td, tillconfig, keyboard, printer
from .models import Session, Payment, Transaction, zero, penny
from decimal import Decimal
import datetime


class _cardpopup(ui.dismisspopup):
    """Ask for card payment details

    A window that pops up whenever a card payment is accepted.  It
    prompts for the card receipt number (provided by the credit card
    terminal) and whether there is any cashback on this transaction.
    """
    def __init__(self, pm, reg, transid, amount, max_cashback, refund=False):
        self.pm = pm
        self.reg = reg
        self.transid = transid
        self.amount = amount
        self.max_cashback = max_cashback
        cashback_in_use = max_cashback > zero
        h = 18 if cashback_in_use else 10
        if self.pm._ask_for_machine_id:
            h += 1
        desc = "refund" if refund else "payment"
        super().__init__(
            h, 44, title=f"Card {desc} transaction {transid}",
            colour=ui.colour_input)
        self.win.wrapstr(
            2, 2, 40, f"Card {desc} of {tillconfig.fc(amount)}")
        y = 4
        fields = []
        if cashback_in_use:
            y += self.win.wrapstr(
                y, 2, 40,
                "Is there any cashback?  Enter the amount and "
                "press Cash/Enter.  Leave blank and press "
                "Cash/Enter if there is none.")
            y += 1
            self.win.drawstr(y, 2, 17, "Cashback amount: ", align=">")
            self.win.addstr(y, 19, tillconfig.currency)
            self.cbfield = ui.moneyfield(y, 19 + len(tillconfig.currency), 6)
            fields.append(self.cbfield)
            y += 2
            self.total_label = ui.label(y, 2, 40)
            y += 2
            self.cbfield.sethook = self.update_total_amount
            self.update_total_amount()
        y += self.win.wrapstr(
            y, 2, 40,
            "Please enter the receipt number from the merchant receipt.")
        y += 1

        if self.pm._ask_for_machine_id:
            self.win.drawstr(y, 2, 17, "Terminal number: ", align=">")
            self.mnfield = ui.editfield(y, 19, 3)
            fields.append(self.mnfield)
            y += 1

        self.win.drawstr(y, 2, 17, "Receipt number: ", align=">")
        self.rnfield = ui.editfield(y, 19, 16)
        fields.append(self.rnfield)
        ui.map_fieldlist(fields)
        fields[0].keymap[keyboard.K_CLEAR] = (self.dismiss, None)
        fields[-1].keymap[keyboard.K_CASH] = (self.enter, None)
        fields[0].focus()

    def update_total_amount(self):
        try:
            cba = Decimal(self.cbfield.f).quantize(penny)
        except:
            cba = zero
        if cba > self.max_cashback:
            self.total_label.set(
                f"Maximum cashback is {tillconfig.fc(self.max_cashback)}",
                colour=ui.colour_error)
        else:
            self.total_label.set(
                f"Total card payment: {tillconfig.fc(self.amount + cba)}")

    def enter(self):
        try:
            cba = Decimal(self.cbfield.f).quantize(penny)
        except:
            cba = zero
        if cba > self.max_cashback:
            self.cbfield.set("")
            self.cbfield.focus()
            return ui.infopopup(
                ["Cashback is limited to a maximum of {} per "
                 "transaction.".format(tillconfig.fc(
                     self.max_cashback))],
                title="Error")
        ref = []
        if self.pm._ask_for_machine_id:
            machineno = self.mnfield.f
            if machineno == "" and self.pm._ref_required:
                self.mnfield.focus()
                return ui.infopopup(["You must enter a card machine id."],
                                    title="Error")
            if machineno:
                ref.append(machineno)

        receiptno = self.rnfield.f
        if receiptno == "" and self.pm._ref_required:
            self.rnfield.focus()
            return ui.infopopup(["You must enter a receipt number."],
                                title="Error")
        if receiptno:
            ref.append(receiptno)

        ref = " ".join(ref)
        self.dismiss()
        self.pm._finish_payment(self.reg, self.transid, self.amount, cba, ref)


class BadCashbackMethod(Exception):
    """Cashback methods must have the change_given=True attribute.
    """
    pass


class CardPayment(payment.PaymentMethod):
    refund_supported = True

    def __init__(self, paytype, description, machines=1, cashback_method=None,
                 max_cashback=zero, kickout=False,
                 rollover_guard_time=None,
                 account_code=None, account_date_policy=None,
                 ask_for_machine_id=False,
                 ref_required=True):
        """Accept payments using a manual PDQ machine.

        This payment method records the receipt number ("reference")
        from the PDQ machine as confirmation, and optionally supports
        cashback.

        The kickout parameter sets whether the cash drawer will be
        opened on a card transaction that does not include cashback.

        rollover_guard_time is the time at which the card terminals
        roll over from recording one day's totals to recording the
        next.  For example, if rollover_guard_time is 3am then
        transactions at 2am on 2nd February will be recorded against
        the card machine totals for 1st February, and transactions at
        4am on 2nd February will be recorded against the card machine
        totals for 2nd February.  This time is determined by the bank;
        it can't be configured directly on the card machines.

        If rollover_guard_time is set then the card machine totals
        date will be checked against the current session's date, and
        the payment will be prevented if it would be recorded against
        the wrong day.

        The ask_for_machine_id parameter sets whether the card
        payment dialog will ask for a card machine id, which will be
        added to the reference field. This only makes sense if you
        have more than one machine.

        If ref_required is set to False then blank entries for machine
        ID (if present) and reference will be permitted and will lead
        to a ref of "" in the database.
        """
        super().__init__(paytype, description)
        self._machines = machines
        self._ask_for_machine_id = ask_for_machine_id if machines > 1 else False
        self._ref_required = ref_required
        self._cashback_method = cashback_method
        if cashback_method and not cashback_method.change_given:
            raise BadCashbackMethod()
        self._max_cashback = max_cashback
        self._kickout = kickout
        self._total_fields = [("Terminal {t}".format(t=t + 1),
                               ui.validate_float, None)
                              for t in range(self._machines)]
        self._rollover_guard_time = rollover_guard_time
        self.account_code = account_code
        self.account_date_policy = account_date_policy

    def describe_payment(self, payment):
        # Card payments use the 'ref' field for the card receipt number
        if payment.amount >= zero:
            return "{}{}{}".format(
                self.description, " " if payment.ref else "", payment.ref)
        return "{} refund{}{}".format(
            self.description, " " if payment.ref else "", payment.ref)

    def start_payment(self, reg, transid, amount, outstanding):
        if self._rollover_guard_time:
            session = Session.current(td.s)
            # session should not be None; this should have been
            # checked in register code before we are called.
            if not session:
                return
            now = datetime.datetime.now()
            date = now.date()
            if now.time() < self._rollover_guard_time:
                date = date - datetime.timedelta(days=1)
            if date != session.date:
                ui.infopopup(
                    ["The card machines 'roll over' from one day to the next at "
                     "around {}, so a card transaction performed now would be "
                     "recorded against the card totals for {}.".format(
                         self._rollover_guard_time, date),
                     "",
                     "The current session is for {}.".format(session.date),
                     "",
                     "Please don't perform a card transaction now.  If you have "
                     "already done one, you must call your manager and let them "
                     "know that the card totals for {} and {} will be "
                     "incorrect.  Set aside the card merchant receipt so that "
                     "it can be entered into the till later.".format(
                         date, session.date)],
                    title="Card transactions not allowed")
                return
        if amount < zero:
            if amount < outstanding:
                ui.infopopup(
                    ["You can't refund more than the amount due back."],
                    title="Refund too large")
                return
            _cardpopup(self, reg, transid, amount, zero, refund=True)
            return
        if amount > outstanding:
            if self._cashback_method:
                ui.infopopup(
                    ["You can't take an overpayment on cards.  If the card "
                     "being used allows cashback, the card terminal "
                     "will prompt you and you can give up to %s back." % (
                            tillconfig.fc(self._max_cashback))],
                    title="Overpayment not accepted")
            else:
                ui.infopopup(
                    ["You can't take an overpayment on cards."],
                    title="Overpayment not accepted")
            return
        _cardpopup(self, reg, transid, amount,
                   self._max_cashback if self._cashback_method else zero)

    def _finish_payment(self, reg, transid, amount, cashback, ref):
        trans = td.s.query(Transaction).get(transid)
        user = ui.current_user().dbuser
        td.s.add(user)
        if not trans or trans.closed:
            ui.infopopup(["The transaction was closed before the payment "
                          "could be recorded.  The payment has been "
                          "ignored."], title="Transaction closed")
            return
        total = amount + cashback
        p = Payment(transaction=trans, paytype=self.get_paytype(),
                    ref=ref, amount=total, user=user)
        td.s.add(p)
        td.s.flush()
        r = [payment.pline(p, method=self)]
        if cashback > zero:
            r.append(self._cashback_method.add_change(
                    trans, "%s cashback" % self.description, zero - cashback))
        if cashback > zero or self._kickout:
            printer.kickout()
        td.s.flush()
        reg.add_payments(transid, r)

    @property
    def total_fields(self):
        return self._total_fields

    def total(self, session, fields):
        try:
            return sum(Decimal(x) if len(x) > 0 else zero for x in fields)
        except:
            return "One or more of the total fields has something " \
                "other than a number in it."

    def accounting_info(self, sessiontotal):
        if not self.account_code:
            return
        if self.account_date_policy:
            date = self.account_date_policy(sessiontotal.session.date)
        else:
            date = sessiontotal.session.date
        return self.account_code, date, "{} takings".format(self.description)
