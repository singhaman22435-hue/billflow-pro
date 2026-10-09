from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from extensions import db
from models.payroll import Employee, Payslip
from models.organization import Organization
from datetime import date, datetime
import io

payroll_bp = Blueprint('payroll', __name__)

def org_id():
    return current_user.org_id

# ─── EMPLOYEES LIST ───────────────────────────────────────
@payroll_bp.route('/payroll/employees')
@login_required
def employees():
    emps = Employee.query.filter_by(org_id=org_id(), is_active=True).order_by(Employee.name).all()
    return render_template('payroll/employees.html', employees=emps)

# ─── ADD EMPLOYEE ─────────────────────────────────────────
@payroll_bp.route('/payroll/employees/add', methods=['GET', 'POST'])
@login_required
def add_employee():
    if request.method == 'POST':
        doj_str = request.form.get('date_of_joining')
        dob_str = request.form.get('date_of_birth')
        emp = Employee(
            org_id=org_id(),
            emp_code=request.form.get('emp_code'),
            name=request.form.get('name'),
            designation=request.form.get('designation'),
            department=request.form.get('department'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            date_of_joining=datetime.strptime(doj_str, '%Y-%m-%d').date() if doj_str else None,
            date_of_birth=datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None,
            pan=request.form.get('pan'),
            aadhar=request.form.get('aadhar'),
            bank_account_no=request.form.get('bank_account_no'),
            bank_ifsc=request.form.get('bank_ifsc'),
            bank_name=request.form.get('bank_name'),
            uan_no=request.form.get('uan_no'),
            basic_salary=request.form.get('basic_salary') or 0,
            hra=request.form.get('hra') or 0,
            special_allowance=request.form.get('special_allowance') or 0,
            other_allowance=request.form.get('other_allowance') or 0,
            pf_applicable=bool(request.form.get('pf_applicable')),
            esi_applicable=bool(request.form.get('esi_applicable')),
            tds_applicable=bool(request.form.get('tds_applicable')),
            tds_monthly=request.form.get('tds_monthly') or 0,
            employment_type=request.form.get('employment_type', 'full_time'),
            created_by=current_user.id
        )
        db.session.add(emp)
        db.session.commit()
        flash(f'✅ Employee {emp.name} added!', 'success')
        return redirect(url_for('payroll.employees'))
    return render_template('payroll/add_employee.html', today=date.today())

# ─── EDIT EMPLOYEE ────────────────────────────────────────
@payroll_bp.route('/payroll/employees/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_employee(id):
    emp = Employee.query.filter_by(id=id, org_id=org_id()).first_or_404()
    if request.method == 'POST':
        doj_str = request.form.get('date_of_joining')
        dob_str = request.form.get('date_of_birth')
        emp.name = request.form.get('name')
        emp.designation = request.form.get('designation')
        emp.department = request.form.get('department')
        emp.email = request.form.get('email')
        emp.phone = request.form.get('phone')
        emp.date_of_joining = datetime.strptime(doj_str, '%Y-%m-%d').date() if doj_str else None
        emp.date_of_birth = datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None
        emp.pan = request.form.get('pan')
        emp.bank_account_no = request.form.get('bank_account_no')
        emp.bank_ifsc = request.form.get('bank_ifsc')
        emp.bank_name = request.form.get('bank_name')
        emp.uan_no = request.form.get('uan_no')
        emp.basic_salary = request.form.get('basic_salary') or 0
        emp.hra = request.form.get('hra') or 0
        emp.special_allowance = request.form.get('special_allowance') or 0
        emp.other_allowance = request.form.get('other_allowance') or 0
        emp.pf_applicable = bool(request.form.get('pf_applicable'))
        emp.esi_applicable = bool(request.form.get('esi_applicable'))
        emp.tds_applicable = bool(request.form.get('tds_applicable'))
        emp.tds_monthly = request.form.get('tds_monthly') or 0
        emp.employment_type = request.form.get('employment_type', 'full_time')
        db.session.commit()
        flash('Employee updated!', 'success')
        return redirect(url_for('payroll.employees'))
    return render_template('payroll/add_employee.html', emp=emp, today=date.today())

# ─── DEACTIVATE EMPLOYEE ──────────────────────────────────
@payroll_bp.route('/payroll/employees/<int:id>/deactivate', methods=['POST'])
@login_required
def deactivate_employee(id):
    emp = Employee.query.filter_by(id=id, org_id=org_id()).first_or_404()
    emp.is_active = False
    db.session.commit()
    flash(f'{emp.name} deactivated.', 'info')
    return redirect(url_for('payroll.employees'))

# ─── PAYROLL RUN (MONTHLY) ────────────────────────────────
@payroll_bp.route('/payroll/run', methods=['GET', 'POST'])
@login_required
def run_payroll():
    org = Organization.query.get(org_id())
    if request.method == 'POST':
        month = request.form.get('month')  # "2024-07"
        emp_ids = request.form.getlist('emp_ids')
        if not month or not emp_ids:
            flash('Select month and at least one employee.', 'danger')
            return redirect(url_for('payroll.run_payroll'))

        created = 0
        for eid in emp_ids:
            emp = Employee.query.filter_by(id=eid, org_id=org_id()).first()
            if not emp:
                continue
            # Check if payslip already exists for this month
            existing = Payslip.query.filter_by(employee_id=emp.id, month=month, org_id=org_id()).first()
            if existing:
                continue

            gross = emp.gross_salary
            pf = emp.pf_deduction
            esi = emp.esi_deduction
            tds = float(emp.tds_monthly or 0)
            total_ded = pf + esi + tds
            net = gross - total_ded

            paid_days = int(request.form.get(f'paid_days_{eid}', 26))
            working_days = int(request.form.get(f'working_days_{eid}', 26))
            # Pro-rate if needed
            if paid_days < working_days:
                factor = paid_days / working_days
                gross = round(gross * factor, 2)
                pf = round(pf * factor, 2)
                esi = round(esi * factor, 2)
                total_ded = pf + esi + tds
                net = gross - total_ded

            ps = Payslip(
                org_id=org_id(),
                employee_id=emp.id,
                month=month,
                payslip_no=f'PS-{month}-{emp.emp_code or emp.id}',
                basic_salary=emp.basic_salary,
                hra=emp.hra,
                special_allowance=emp.special_allowance,
                other_allowance=emp.other_allowance,
                gross_earnings=gross,
                pf_deduction=pf,
                esi_deduction=esi,
                tds_deduction=tds,
                total_deductions=total_ded,
                net_salary=net,
                working_days=working_days,
                paid_days=paid_days,
                created_by=current_user.id
            )
            db.session.add(ps)
            created += 1

        db.session.commit()
        flash(f'✅ {created} payslip(s) generated for {month}!', 'success')
        return redirect(url_for('payroll.payslip_list'))

    employees = Employee.query.filter_by(org_id=org_id(), is_active=True).order_by(Employee.name).all()
    current_month = date.today().strftime('%Y-%m')
    return render_template('payroll/run_payroll.html', employees=employees, current_month=current_month)

# ─── PAYSLIPS LIST ────────────────────────────────────────
@payroll_bp.route('/payroll/payslips')
@login_required
def payslip_list():
    month = request.args.get('month', date.today().strftime('%Y-%m'))
    payslips = Payslip.query.filter_by(org_id=org_id(), month=month).order_by(Payslip.id.desc()).all()
    total_gross = sum(float(p.gross_earnings or 0) for p in payslips)
    total_net = sum(float(p.net_salary or 0) for p in payslips)
    total_pf = sum(float(p.pf_deduction or 0) for p in payslips)
    return render_template('payroll/payslips.html', payslips=payslips, month=month,
                           total_gross=total_gross, total_net=total_net, total_pf=total_pf)

# ─── VIEW / DOWNLOAD PAYSLIP ──────────────────────────────
@payroll_bp.route('/payroll/payslips/<int:id>')
@login_required
def view_payslip(id):
    ps = Payslip.query.filter_by(id=id, org_id=org_id()).first_or_404()
    org = Organization.query.get(org_id())
    return render_template('payroll/view_payslip.html', ps=ps, org=org)

@payroll_bp.route('/payroll/payslips/<int:id>/pdf')
@login_required
def download_payslip_pdf(id):
    ps = Payslip.query.filter_by(id=id, org_id=org_id()).first_or_404()
    org = Organization.query.get(org_id())
    try:
        from utils.pdf_generator import generate_payslip_pdf
        pdf_bytes = generate_payslip_pdf(ps, org)
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'{ps.payslip_no}.pdf'
        )
    except Exception as e:
        flash(f'PDF error: {str(e)}', 'danger')
        return redirect(url_for('payroll.view_payslip', id=id))

@payroll_bp.route('/payroll/payslips/<int:id>/mark-paid', methods=['POST'])
@login_required
def mark_paid(id):
    ps = Payslip.query.filter_by(id=id, org_id=org_id()).first_or_404()
    ps.paid = True
    ps.paid_date = date.today()
    ps.payment_mode = request.form.get('payment_mode', 'bank')
    db.session.commit()
    flash(f'Payslip marked as paid!', 'success')
    return redirect(url_for('payroll.payslip_list', month=ps.month))

@payroll_bp.route('/payroll')
@login_required
def index():
    return redirect(url_for('payroll.employees'))
