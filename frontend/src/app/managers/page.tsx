'use client';

import PeopleResourcePage, { type PeopleResourceConfig } from '@/components/common/PeopleResourcePage';
import {
  createManager,
  getManager,
  getManagers,
  updateManager,
  type ManagerRecord,
} from '@/services/api';

const config: PeopleResourceConfig<ManagerRecord> = {
  title: 'Managers',
  description: 'Manage manager profiles, effective periods, and reporting team sizes.',
  fields: [
    { key: 'employee_id', label: 'Employee ID', required: true },
    { key: 'effective_from', label: 'Effective from', type: 'date', required: true },
    { key: 'effective_to', label: 'Effective to', type: 'date', nullable: true },
    { key: 'status', label: 'Status', type: 'select', required: true, options: ['active', 'inactive'] },
  ],
  columns: [
    { key: 'id', label: 'Manager ID' },
    { key: 'employee_name', label: 'Employee' },
    { key: 'department', label: 'Department' },
    { key: 'report_count', label: 'Direct reports' },
    { key: 'status', label: 'Status' },
  ],
  list: getManagers,
  get: getManager,
  create: (payload) => createManager(payload as Parameters<typeof createManager>[0]),
  update: (id, payload) => updateManager(id, payload as Parameters<typeof updateManager>[1]),
};

export default function ManagersPage() {
  return <PeopleResourcePage config={config} />;
}
