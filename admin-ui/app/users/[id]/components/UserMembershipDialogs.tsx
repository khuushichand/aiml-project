'use client';

import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import type { OrgMembership, TeamMembership } from '@/types';

interface UserMembershipDialogsProps {
  showOrgMembershipsDialog: boolean;
  showTeamMembershipsDialog: boolean;
  orgMemberships: OrgMembership[];
  teamMemberships: TeamMembership[];
  orgMembershipsLoading: boolean;
  teamMembershipsLoading: boolean;
  orgMembershipsError: string;
  teamMembershipsError: string;
  onOpenOrgMembershipsChange: (open: boolean) => void;
  onOpenTeamMembershipsChange: (open: boolean) => void;
}

export function UserMembershipDialogs({
  showOrgMembershipsDialog,
  showTeamMembershipsDialog,
  orgMemberships,
  teamMemberships,
  orgMembershipsLoading,
  teamMembershipsLoading,
  orgMembershipsError,
  teamMembershipsError,
  onOpenOrgMembershipsChange,
  onOpenTeamMembershipsChange,
}: UserMembershipDialogsProps) {
  return (
    <>
      <Dialog open={showOrgMembershipsDialog} onOpenChange={onOpenOrgMembershipsChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>User Organizations</DialogTitle>
            <DialogDescription>
              Organizations this user belongs to and their role in each organization.
            </DialogDescription>
          </DialogHeader>
          {orgMembershipsError && (
            <Alert variant="destructive">
              <AlertDescription>{orgMembershipsError}</AlertDescription>
            </Alert>
          )}
          {orgMembershipsLoading ? (
            <div className="text-sm text-muted-foreground">Loading organizations...</div>
          ) : orgMemberships.length === 0 ? (
            <div className="text-sm text-muted-foreground">No organization memberships found.</div>
          ) : (
            <div className="max-h-80 overflow-y-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Organization</TableHead>
                    <TableHead>Role</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {orgMemberships.map((membership) => (
                    <TableRow key={membership.org_id}>
                      <TableCell className="text-sm">
                        {membership.org_name || `Organization ${membership.org_id}`}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{membership.role}</Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => onOpenOrgMembershipsChange(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showTeamMembershipsDialog} onOpenChange={onOpenTeamMembershipsChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>User Teams</DialogTitle>
            <DialogDescription>
              Team memberships with organization context and assigned role.
            </DialogDescription>
          </DialogHeader>
          {teamMembershipsError && (
            <Alert variant="destructive">
              <AlertDescription>{teamMembershipsError}</AlertDescription>
            </Alert>
          )}
          {teamMembershipsLoading ? (
            <div className="text-sm text-muted-foreground">Loading teams...</div>
          ) : teamMemberships.length === 0 ? (
            <div className="text-sm text-muted-foreground">No team memberships found.</div>
          ) : (
            <div className="max-h-80 overflow-y-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Team</TableHead>
                    <TableHead>Organization</TableHead>
                    <TableHead>Role</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {teamMemberships.map((membership) => (
                    <TableRow key={`${membership.org_id}-${membership.team_id}`}>
                      <TableCell className="text-sm">
                        {membership.team_name || `Team ${membership.team_id}`}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {membership.org_name || `Organization ${membership.org_id}`}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{membership.role}</Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => onOpenTeamMembershipsChange(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
