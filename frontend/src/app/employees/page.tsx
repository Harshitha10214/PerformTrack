'use client';

import PeopleResourcePage, { type PeopleResourceConfig } from '@/components/common/PeopleResourcePage';
import {
  createEmployee,
  getEmployee,
  getEmployees,
  updateEmployee,
  type EmployeeRecord,
} from '@/services/api';

const config: PeopleResourceConfig<EmployeeRecord> = {
  title: 'Employees',
  description: 'Search and maintain employee profiles and reporting relationships.',
  fields: [
    { key: 'email', label: 'Work email', type: 'email', required: true },
    { key: 'first_name', label: 'First name', required: true },
    { key: 'last_name', label: 'Last name', required: true },
    { key: 'job_title', label: 'Job title', required: true },
    { key: 'department', label: 'Department', required: true },
    { key: 'hire_date', label: 'Hire date', type: 'date', required: true },
    { key: 'effective_from', label: 'Effective from', type: 'date', required: true },
    { key: 'effective_to', label: 'Effective to', type: 'date', nullable: true },
    { key: 'status', label: 'Status', type: 'select', required: true, options: ['active', 'leave', 'inactive', 'terminated'] },
    { key: 'manager_id', label: 'Manager ID (optional)', nullable: true },
  ],
  columns: [
    { key: 'id', label: 'Employee ID' },
    { key: 'first_name', label: 'First name' },
    { key: 'last_name', label: 'Last name' },
    { key: 'job_title', label: 'Job title' },
    { key: 'department', label: 'Department' },
    { key: 'status', label: 'Status' },
  ],
  list: getEmployees,
  get: getEmployee,
  create: (payload) => createEmployee(payload as Omit<EmployeeRecord, 'id' | 'created_at' | 'updated_at'>),
  update: (id, payload) => updateEmployee(id, payload as Partial<Omit<EmployeeRecord, 'id' | 'created_at' | 'updated_at'>>),
};

export default function EmployeesPage() {
  return <PeopleResourcePage config={config} />;
}
