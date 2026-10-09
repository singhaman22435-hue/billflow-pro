from extensions import db
from datetime import datetime

class Employee(db.Model):
    """Employee for Payroll Management"""
    __tablename__ = 'employees'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    emp_code = db.Column(db.String(20))
    name = db.Column(db.String(200), nullable=False)
    designation = db.Column(db.String(100))
    department = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    date_of_joining = db.Column(db.Date)
    date_of_birth = db.Column(db.Date)
    pan = db.Column(db.String(20))
    aadhar = db.Column(db.String(20))
    bank_account_no = db.Column(db.String(50))
    bank_ifsc = db.Column(db.String(20))
    bank_name = db.Column(db.String(100))
    uan_no = db.Column(db.String(20))  # UAN for PF

    # Salary Components (monthly)
    basic_salary = db.Column(db.Numeric(12, 2), default=0)
    hra = db.Column(db.Numeric(12, 2), default=0)
    special_allowance = db.Column(db.Numeric(12, 2), default=0)
    other_allowance = db.Column(db.Numeric(12, 2), default=0)

    # Deductions
    pf_applicable = db.Column(db.Boolean, default=True)    # PF = 12% of basic
    esi_applicable = db.Column(db.Boolean, default=False)  # ESI if salary < 21000
    tds_applicable = db.Column(db.Boolean, default=False)
    tds_monthly = db.Column(db.Numeric(12, 2), default=0)  # Fixed monthly TDS

    employment_type = db.Column(db.String(20), default='full_time')  # full_time/part_time/contract
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    payslips = db.relationship('Payslip', backref='employee', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def gross_salary(self):
        return float(self.basic_salary or 0) + float(self.hra or 0) + \
               float(self.special_allowance or 0) + float(self.other_allowance or 0)

    @property
    def pf_deduction(self):
        if self.pf_applicable:
            return round(float(self.basic_salary or 0) * 0.12, 2)
        return 0

    @property
    def esi_deduction(self):
        if self.esi_applicable and self.gross_salary <= 21000:
            return round(self.gross_salary * 0.0075, 2)  # 0.75% employee contribution
        return 0

    @property
    def net_salary(self):
        return round(self.gross_salary - self.pf_deduction - self.esi_deduction - float(self.tds_monthly or 0), 2)

    def __repr__(self):
        return f'<Employee {self.name}>'


class Payslip(db.Model):
    """Monthly Salary Slip"""
    __tablename__ = 'payslips'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    month = db.Column(db.String(7), nullable=False)  # "2024-07"
    payslip_no = db.Column(db.String(30))

    # Earnings (copied at time of generation)
    basic_salary = db.Column(db.Numeric(12, 2), default=0)
    hra = db.Column(db.Numeric(12, 2), default=0)
    special_allowance = db.Column(db.Numeric(12, 2), default=0)
    other_allowance = db.Column(db.Numeric(12, 2), default=0)
    bonus = db.Column(db.Numeric(12, 2), default=0)
    overtime = db.Column(db.Numeric(12, 2), default=0)
    gross_earnings = db.Column(db.Numeric(12, 2), default=0)

    # Deductions
    pf_deduction = db.Column(db.Numeric(12, 2), default=0)
    esi_deduction = db.Column(db.Numeric(12, 2), default=0)
    tds_deduction = db.Column(db.Numeric(12, 2), default=0)
    other_deduction = db.Column(db.Numeric(12, 2), default=0)
    total_deductions = db.Column(db.Numeric(12, 2), default=0)

    net_salary = db.Column(db.Numeric(12, 2), default=0)
    working_days = db.Column(db.Integer, default=26)
    paid_days = db.Column(db.Integer, default=26)

    paid = db.Column(db.Boolean, default=False)
    paid_date = db.Column(db.Date)
    payment_mode = db.Column(db.String(20), default='bank')
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Payslip {self.payslip_no}>'
