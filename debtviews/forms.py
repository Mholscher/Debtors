#    Copyright 2020 Menno Hölscher
#
#    This file is part of debtors.

#    debtors is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

#    debtors is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.

#    You should have received a copy of the GNU Lesser General Public License
#    along with debtors.  If not, see <http://www.gnu.org/licenses/>.

""" This module holds the form necessary to create and change bills 

The manual changes to and creation of bills needs forms. This module 
holds these forms.
"""

from flask_wtf import FlaskForm
from wtforms import HiddenField, StringField, DateField, SubmitField,\
    IntegerField, SelectField
from wtforms.validators import DataRequired, Length, Optional, ValidationError
from flask_wtf.csrf import CSRFProtect
from debtmodels.debtbilling import Bills, ReplacedBillError


class PrevBillMustExist(ValueError):
    """ WTForms validator for existence of a previous bill
    
    If we want to replace an existing bill, the number passed in for
    that previous bill must denote an existing bill.
    """

    def __init__(self, message=None):

        message = 'No bill to replace'

        if message:
            self.message = message

    def __call__(self, form, field):

        try:
            Bills.check_prev_bill(field)
        except ReplacedBillError as rbe:
            raise ValidationError(str(rbe))


class BillForm(FlaskForm):
    """ This holds parts of the form for creating and changing bills """

    
    bill_id = HiddenField('bill id')
    csrf_token = HiddenField('csrf_token')
    billing_ccy = StringField('Billing currency', validators=[Length(max=3)])
    bill_replaced = IntegerField('Bill to be replaced',
                                 validators=[Optional(), PrevBillMustExist()])


class BillCreateForm(BillForm):
    """ This is the form for creating a new bill """

    client_id = StringField('Client number')
    date_sale = DateField('Date of sale', format='%d-%m-%Y', 
                          validators=[DataRequired()])
    add_1 = SubmitField('Update & exit')
    add_more = SubmitField('Update & new')
    

class BillChangeForm(BillForm):
    """ This is the form for canging an existing bill """

    client_id = StringField('Client number', validators=[Optional()])
    date_sale = DateField('Date of sale', format='%d-%m-%Y')
    update = SubmitField('Update')
    

