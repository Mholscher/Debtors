#    Copyright 2021 Menno Hölscher
#
#    This file is part of Debtors.

#    Debtors is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

#    Debtors is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.

#    You should have received a copy of the GNU Lesser General Public License
#    along with Debtors.  If not, see <http://www.gnu.org/licenses/>.

import os, os.path
import unittest
from os.path import exists
from datetime import date
from debtors import db
from debttests.helpers import (create_clients, add_addresses,
                               create_bills, add_lines_to_bills,
                               delete_test_bills, delete_test_prefs,
                               delete_test_clients, create_payments_for_overdue,
                               delete_test_payments)
from debtviews.monetary import edited_amount
from debtmodels.overdue import (OverdueProcessor, ProcessorAlreadyExistsError,
                                OverdueSteps)
from debtmodels.overdue_processors import FirstLetterProcessor
from debtviews.physicaloverdue import PaperLetter, OverdueDictView


class TestCreateOverdueDict(unittest.TestCase):

    def setUp(self):


        create_clients(self)
        add_addresses(self)
        create_bills(self)
        add_lines_to_bills(self)
        create_payments_for_overdue(self)
        db.session.flush()

    def tearDown(self):

        OverdueProcessor.all_processors.clear()
        db.session.rollback()
        delete_test_payments(self)
        delete_test_bills(self)
        delete_test_prefs(self)
        delete_test_clients(self)
        db.session.commit()

    def test_overdue_has_bill_data(self):
        """ An overdue dictionary should contain data for bill  """

        view = OverdueDictView(bill_id=self.bll4.bill_id)
        self.assertIn("bill", view, 'Bill not in overdue view')

    def test_correct_data_in_bill(self):
        """ Some must have items are in the dictionary """

        view = OverdueDictView(bill_id=self.bll4.bill_id)
        self.assertIn("bill_id", view["bill"], 'Bill id not in overdue view')
        self.assertIn("billing_ccy", view["bill"], 'Currency not in overdue view')
        self.assertEqual("Yen", view["bill"]["billing_ccy"],
                         'Currency incorrect/missing in overdue view')
        self.assertEqual("1.880", view["bill"]["total"],
                         'Bill total incorrect in overdue view')

    def test_overdue_has_client_data(self):
        """ An overdue dictionary should contain client data """

        view = OverdueDictView(bill_id=self.bll4.bill_id)
        self.assertIn("client", view, 'Client not in overdue view')
        self.assertIn("surname", view["client"], "Client surname not in view")
        self.assertIn("town_or_village", view["client"],
                      "Client town not in view")

    def test_overdue_has_payment_list(self):
        """ Overdue data has a list of open payments received """

        view = OverdueDictView(bill_id=self.bll4.bill_id)
        self.assertIn("payments", view, "No payments in overdue view")

    def test_payment_in_payment_list(self):
        """ The payment list has a payment for the client """

        view = OverdueDictView(bill_id=self.bll4.bill_id)
        self.assertEqual(edited_amount(self.ia110.payment_amount,
                                       currency=self.ia110.payment_ccy),
                         view["payments"][0]["payment_amount"],
                         "Payment not in list")

    def test_currency_converted(self):
        """ The currency must be converted to non-ISO form """

        view = OverdueDictView(bill_id=self.bll4.bill_id)
        self.assertEqual("Yen",
                         view["payments"][0]["payment_ccy"],
                         "Payment currency not correct")

    def test_list_other_bills(self):
        """ There must be a list of other bill than the one triggering """

        view = OverdueDictView(bill_id=self.bll4.bill_id)
        self.assertIn("morebills", view, "No other bills in overdue view")

    def test_other_bill_data(self):
        """ Bills in list have valid data  """

        view = OverdueDictView(bill_id=self.bll4.bill_id)
        other_bills = view["morebills"]
        bill7 = [bill for bill in other_bills
                 if bill["bill_id"] == self.bll7.bill_id][0]
        self.assertEqual("Yen", bill7["billing_ccy"], "Currency not correct")
        self.assertEqual(edited_amount(self.bll7.total(),
                                       currency=self.bll7.billing_ccy),
                                       bill7["total"],
                                       "Amount not correct")
        self.assertEqual(self.bll7.date_sale.strftime("%d-%m-%Y"),
                         bill7["date_sale"], "Due date not correct")

class TestCreateFirstLetterProcessor(unittest.TestCase):

    def tearDown(self):

        OverdueProcessor.all_processors.clear()

    def test_create_processor(self):
        """ Create a firstletter processor """

        flp01 = FirstLetterProcessor()
        self.assertIn(flp01.processor_key, flp01.all_processors,
                      "Processor not added to all_processors")

    def test_create_second_processor_fails(self):
        """ Can not create a duplicate processor """

        flp02 = FirstLetterProcessor()
        with self.assertRaises(ProcessorAlreadyExistsError):
            flp03 = FirstLetterProcessor()

class TestFirstLetterProcess(unittest.TestCase):

    def setUp(self):

        self.flp04 = FirstLetterProcessor()
        create_clients(self)
        add_addresses(self)
        create_bills(self)
        add_lines_to_bills(self)
        self.st11 = OverdueSteps(id=100, number_of_days=25, 
                                step_name="First Letter",
                                processor="firstletter")
        self.st11.add()
        db.session.flush()

    def tearDown(self):

        OverdueProcessor.all_processors.clear()
        db.session.rollback()
        delete_test_bills(self)
        delete_test_prefs(self)
        delete_test_clients(self)
        db.session.commit()

    def test_execute(self):
        """ Execute produces a first letter """

        dates_list = OverdueSteps.get_date_list(from_date=date(2020, 3, 18))
        for proc_data in dates_list:
            if proc_data[2] == self.flp04.processor_key:
                current_processor_data = proc_data
                break
        self.assertTrue(self.flp04, "No key {flp04.processor_key} found")
        self.flp04.execute(self.bll4, processor_data=current_processor_data)
        self.assertTrue(exists("output/fl" + str(self.bll4.bill_id)),
                               "First letter file does not exist")

    def test_mail_if_preference_mail(self):
        """ If letter preference of client is mail, also mail is made """

        dates_list = OverdueSteps.get_date_list(from_date=date(2020, 3, 18))
        for proc_data in dates_list:
            if proc_data[2] == self.flp04.processor_key:
                current_processor_data = proc_data
                break
        self.assertTrue(self.flp04, "No key {flp04.processor_key} found")
        self.flp04.execute(self.bll8, processor_data=current_processor_data)
        self.assertTrue(exists("output/mailfom" + str(self.bll8.bill_id)),
                               "First letter mail does not exist")


class TestFirstLetterContent(unittest.TestCase):

    def setUp(self):

        self.flp05 = FirstLetterProcessor()
        create_clients(self)
        add_addresses(self)
        create_bills(self)
        add_lines_to_bills(self)
        create_payments_for_overdue(self)
        db.session.flush()

    def tearDown(self):

        OverdueProcessor.all_processors.clear()
        db.session.rollback()
        delete_test_bills(self)
        delete_test_payments(self)
        delete_test_prefs(self)
        delete_test_clients(self)
        db.session.commit()

    def test_instantiated_template_in_output(self):
        """ The template is in the output """

        bill = self.bll4
        template = "firstletter.rtf"
        template_text = PaperLetter(template_name=template, bill=bill)
        self.assertIn("Testcompany", template_text.text, "Testcompany not in text")

    def test_data_in_template(self):
        """ The data passed in from the datbase is in the text """

        bill = self.bll4
        template = "firstletter.rtf"
        template_text = PaperLetter(template_name=template, bill=bill)
        self.assertIn("Yen", template_text.text,
                      "Bill currency  not in text")

    def test_other_bill_other_currency(self):
        """ Bill in a different currency shows currency """

        bill = self.bll4
        template = "firstletter.rtf"
        template_text = PaperLetter(template_name=template, bill=bill)
        self.assertIn("Euro", template_text.text,
                      "Differing bill currency  not in text")

    def test_payment_on_doc(self):
        """ An unassigned payment from the bill's client is in the letter """

        bill = self.bll4
        template = "firstletter.rtf"
        template_text = PaperLetter(template_name=template, bill=bill)
        self.assertIn("28", template_text.text,
                      "Payment amount not in text")
        self.assertNotIn(",28", template_text.text,
                      "Payment amount wrongly formatted")

    def test_bill_status_limited_to_issued(self):
        """ Only issued bills appear on a first letter """

        bill = self.bll4
        template = "firstletter.rtf"
        template_text = PaperLetter(template_name=template, bill=bill)
        self.assertNotIn(str(self.bll5.bill_id), template_text.text,
                         "Paid bill in text")

    def test_assigned_payment_not_in_letter(self):
        """ An assigned amount should not be in the letter  """

        self.ia111.assign_to_amount(self.ia112)
        self.assertTrue(self.ia111.fully_assigned, "Open amount on payment")
        bill = self.bll8
        template = "firstletter.rtf"
        template_text = PaperLetter(template_name=template, bill=bill)
        self.assertNotIn(str(self.ia111.id), template_text.text,
                         "Assigned amount in text")


class TestFirstLetterMailContent(unittest.TestCase):

    def setUp(self):
        self.flp06 = FirstLetterProcessor()
        create_clients(self)
        add_addresses(self)
        create_bills(self)
        add_lines_to_bills(self)
        create_payments_for_overdue(self)
        self.st12 = OverdueSteps(id=100, number_of_days=25, 
                                step_name="First Letter",
                                processor="firstletter")
        self.st12.add()
        db.session.flush()

    def tearDown(self):

        OverdueProcessor.all_processors.clear()
        db.session.rollback()
        delete_test_bills(self)
        delete_test_payments(self)
        delete_test_prefs(self)
        delete_test_clients(self)
        db.session.commit()

    def test_bill_id_in_mail(self):
        """ The id of a bill needs to be present in the mail """

        dates_list = OverdueSteps.get_date_list(from_date=date(2020, 3, 18))
        for proc_data in dates_list:
            if proc_data[2] == self.flp06.processor_key:
                current_processor_data = proc_data
                break
        self.assertTrue(self.flp06, "No key {flp06.processor_key} found")
        self.flp06.execute(self.bll8, processor_data=current_processor_data)
        with open("output/mailfom" + str(self.bll8.bill_id), "rt") as e_mail:
            mail_text = e_mail.read()
        self.assertIn(str(self.bll8.bill_id), mail_text,
                      "Open bill not in text")
        self.assertNotIn(str(self.bll1.bill_id), mail_text,
                         "Paid bill in text")

    def test_payment_in_mail(self):
        """ A first letter mail must contain payments """

        dates_list = OverdueSteps.get_date_list(from_date=date(2020, 3, 18))
        for proc_data in dates_list:
            if proc_data[2] == self.flp06.processor_key:
                current_processor_data = proc_data
                break
        self.assertTrue(self.flp06, "No key {flp06.processor_key} found")
        self.flp06.execute(self.bll8, processor_data=current_processor_data)
        with open("output/mailfom" + str(self.bll8.bill_id), "rt") as e_mail:
            mail_text = e_mail.read()
        self.assertIn(str(self.ia111.id), mail_text,
                      "Payment not found in mail")

    def test_assigned_payment_not_in_mail(self):
        """ An assigned payment should not be in mail """

        self.ia111.assign_to_amount(self.ia112)
        self.assertTrue(self.ia111.fully_assigned, "Open amount on payment")
        dates_list = OverdueSteps.get_date_list(from_date=date(2020, 3, 18))
        for proc_data in dates_list:
            if proc_data[2] == self.flp06.processor_key:
                current_processor_data = proc_data
                break
        self.assertTrue(self.flp06, "No key {flp06.processor_key} found")
        self.flp06.execute(self.bll8, processor_data=current_processor_data)
        with open("output/mailfom" + str(self.bll8.bill_id), "rt") as e_mail:
            mail_text = e_mail.read()
        self.assertNotIn(str(self.ia111.id), mail_text,
                      "Assigned payment found in mail")


if __name__ == '__main__' :
    unittest.main()