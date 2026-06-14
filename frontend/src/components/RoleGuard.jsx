import React from 'react';

export default function RoleGuard({ user, allowedRoles, fallback = null, children }) {
  const userRole = user?.role || 'guest';
  if (allowedRoles.includes(userRole)) {
    return children;
  }
  return fallback;
}
