# -*- coding: utf-8 -*-
#
# Copyright © 2008  Ricky Zhou All rights reserved.
# Copyright © 2008-2009 Red Hat, Inc. All rights reserved.
#
# This copyrighted material is made available to anyone wishing to use, modify,
# copy, or redistribute it subject to the terms and conditions of the GNU
# General Public License v.2.  This program is distributed in the hope that it
# will be useful, but WITHOUT ANY WARRANTY expressed or implied, including the
# implied warranties of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.  You should have
# received a copy of the GNU General Public License along with this program;
# if not, write to the Free Software Foundation, Inc., 51 Franklin Street,
# Fifth Floor, Boston, MA 02110-1301, USA. Any Red Hat trademarks that are
# incorporated in the source code or documentation are not subject to the GNU
# General Public License and may only be used or replicated with the express
# permission of Red Hat, Inc.
#
# Author(s): Ricky Zhou <ricky@fedoraproject.org>
#            Mike McGrath <mmcgrath@redhat.com>
#            Toshio Kuratomi <toshio@redhat.com>
#

import re

from turbogears import config
import turbogears

from sqlalchemy.exceptions import InvalidRequestError

from fas.model import PersonRoles

def isAdmin(person):
    '''Checks if the user is a FAS admin

    :arg person: `identity.current`, `People` object, or username to determine
        whether they are in the admin group
    :returns: True if the user is a FAS admin (a member of the admingroup)
        otherwise False
    '''
    admingroup = config.get('admingroup')
    if isinstance(person, turbogears.identity.IdentityWrapper):
        # Save a db lookup when using an identity
        if admingroup in person.groups:
            return True
    elif isinstance(person, basestring):
        # Username
        try:
            PersonRoles.query.filter_by(role_status='approved').join('group'
                    ).filter_by(name=admingroup).join('member'
                            ).filter_by(username=person).one()
            return True
        except InvalidRequestError:
            pass
    else:
        # People object
        try:
            if person.group_roles[admingroup].role_status == 'approved':
                return True
        except KeyError:
            pass
    return False

def canAdminGroup(person, group, role=None):
    '''Checks if the user is allowed to act as an admin for a group

    :arg person: People object or username to check for admin role
    :arg group: Groups object to find out if the person is an admin for
    :kwarg role: If given, the person's role in the group.  If not given, this
        is looked up from the db
    :returns: True if the person can admin this group otherwise False
    '''
    if isAdmin(person):
        return True
    if isinstance(person, basestring):
        if group.owner.username == person:
            return True
        if not role:
            try:
                PersonRoles.query.filter_by(group=group, role_status='approved',
                        role_type='administrator').join('member'
                                ).filter_by(username=person).one()
                return True
            except InvalidRequestError:
                # Not in the group
                pass
    else:
        if group.owner == person:
            return True
        if not role:
            try:
                PersonRoles.query.filter_by(group=group, member=person,
                        role_status='approved', role_type='administrator').one()
                return True
            except InvalidRequestError:
                # Not in the group
                pass
    if role and role.role_status == 'approved' and \
            role.role_type == 'administrator':
        return True
    return False

def canSponsorGroup(person, group):
    '''Checks if the user is allowed to act as a sponsor for a group

    :arg person: People object or username to check whether they can sponsor
    :arg group: Groups object to find out if the person is a sponsor for
    :returns: True if the user is allowed to act as a sponsor for a group
        otherwise False
    '''
    # Check this first as it trumps the other checks
    if isAdmin(person):
        return True
    if isinstance(person, basestring):
        if group.owner.username == person:
            return True
        try:
            role = PersonRoles.query.filter_by(group=group).join('member'
                    ).filter_by(username=person).one()
        except InvalidRequestError:
            # Not in the group
            pass
    else:
        if group.owner == person:
            return True
        try:
            role = PersonRoles.query.filter_by(group=group, member=person).one()
        except InvalidRequestError:
            # Not in the group
            pass

    if role and ((role.role_status == 'approved' and \
            role.role_type == 'sponsor') or canAdminGroup(person, group, role)):
        return True
    return False

def isApproved(person, group):
    '''Check if the user is an approved member of a group.

    :arg person: People object or username to check if they're an approved
        member of the group.
    :arg group: Group object to check if the person is an approved member of
    Returns True if the user is an approved member of a group
    '''
    if isinstance(person, basestring):
        try:
            PersonRoles.query.filter_by(group=group, role_status='approved'
                    ).join('member').filter_by(username=person).one()
            return True
        except InvalidRequestError:
            pass
    else:
        try:
            if person.group_roles[group.name].role_status == 'approved':
                return True
        except KeyError:
            # Not in this group
            pass
    return False

def CLADone(person):
    '''Checks if the user has completed the CLA.

    :arg person: People object or username to check for CLA status
    :returns: True if the user has completed the CLA otherwise False
    '''
    cla_done_group = config.get('cla_done_group')
    if isinstance(person, basestring):
        try:
            PersonRoles.query.filter_by(role_status='approved').join('group'
                    ).filter_by(name=cla_done_group).join('member'
                            ).filter_by(username=person).one()
            return True
        except InvalidRequestError:
            # Not in the group
            pass
    try:
        if person.group_roles[cla_done_group].role_status == 'approved':
            return True
    except KeyError:
        # Not in the group
        pass
    return False

def canEditUser(person, target):
    '''Check whether the user has privileges to edit the target user.

    :arg person: People object or username to check for privileges
    :arg target: People object or username to see if the `person` has edit
        privileges on
    :returns: True if `person` has privileges to edit `target` user
    '''
    p_is_string = isinstance(person, basestring)
    t_is_string = isinstance(target, basestring)
    if p_is_string == t_is_string:
        # person and target are same type, can directly compare
        if person == target:
            return True
    # Otherwise we have to compare the username of the object
    elif p_is_string:
        if person == target.username:
            return True
    else:
        if person.username == target:
            return True

    if isAdmin(person):
        return True

    return False

def canCreateGroup(person):
    '''Check whether the user can create groups

    :arg person: People object or username to check if they can create groups
    :returns: True if the user can create groups else False
    '''
    # Should groupname restrictions go here?
    if isAdmin(person):
        return True
    if isinstance(person, basestring):
        try:
            PersonRoles.query.filter_by(role_status='approved').join('group'
                    ).filter_by(name='sysadmin').join('member').filter_by(
                            username=person)
            return True
        except InvalidRequestError:
            # Not in group
            pass
    else:
        try:
            # isApproved is more appropriate here, but that would require an extra
            # group.by_name.  I need to think over the efficiency of auth.py.
            # Maybe something in model.py so that Any given query should only be
            # called once...
            if person.group_roles['sysadmin'].role_status == 'approved':
                return True
        except KeyError:
            # Not in the group
            pass
    return False

def canEditGroup(person, group):
    '''Check if the person can edit the group information

    :arg person: People object or username to check for privileges to edit the
        group
    :arg group: Groups object to check if `person` can edit
    :returns: True if the user can edit the group otherwise False
    '''
    return canAdminGroup(person, group)

def canViewGroup(person, group):
    '''Check if the user can view the group

    :arg person: People object or username to check for privleges to view the
        group
    :arg group: Group object to see if `person` can view
    :returns: True if the user can view the group otherwise False
    '''
    # If the group matched by privileged_view_groups, then
    # only people that can admin the group can view it
    privilegedViewGroups = config.get('privileged_view_groups')
    if re.compile(privilegedViewGroups).match(group.name):
        if not canAdminGroup(person, group):
            return False
    return True

def canApplyGroup(person, group, applicant):
    '''Check whether the user can apply applicant to the group.

    :arg person: People object or username to test whether they can apply an
        applicant
    :arg group: Group object to apply to
    :arg applicant: People object for the person to be added to the group.
    :returns: True if the user can apply applicant to the group otherwise False
    '''
    # User must satisfy all dependencies to join.
    # This is bypassed for people already in the group and for the
    # owner of the group (when they initially make it).
    prerequisite = group.prerequisite
    # TODO: Make this raise more useful info.
    if prerequisite:
        if prerequisite not in applicant.approved_memberships:
            turbogears.flash(_('%s membership required before application to this group is allowed') % prerequisite.name)
            return False

    # group sponsors can apply anybody.
    if canSponsorGroup(person, group):
        return True

    # TODO: We can implement invite-only groups here instead.
    if group.group_type not in ('system',) and ( \
            (isinstance(person, basestring) and person == applicant.username) \
            or (person == applicant)):
        return True

    return False

def canSponsorUser(person, group, target):
    '''Check whether the user can sponsor target in the group


    :arg person: People object or username to check for permission
    :arg group: Group object to check if `person` has permission
    :arg target: People object to see if `person` can sponsor into `group`
    :returns: True if the user can sponsor target in the group otherwise False
    '''
    # This is just here in case we want to add more complex checks in the
    # future 
    return canSponsorGroup(person, group)

def canRemoveUser(person, group, target):
    '''Check whether the person can remove a target user from the group.

    :arg person: People object or username to check for permission
    :arg group: Group object to check if `person` has permission
    :arg target: People object to see if `person` can remove from `group`
    :returns: True if the user can remove target from the group otherwise False
    '''
    # Only administrators can remove administrators.
    if canAdminGroup(target, group) and \
        not canAdminGroup(person, group):
        return False
    # A user can remove themself from a group if user_can_remove is 1
    # Otherwise, a sponsor can remove sponsors/users.
    elif (((isinstance(person, basetring) and person == target.username) \
            or person == target) and (group.user_can_remove == True)) or \
        canSponsorGroup(person, group):
        return True
    return False

def canUpgradeUser(person, group, target):
    '''Check whether the person can upgrade the target in the group.

    :arg person: People object or username to check for permissions to upgrade
    :arg group: Group object to check whether `person` can upgrade in
    :arg target: People object to check if `person` can upgrade
    :returns: True if the user can upgrade target in the group otherwise False
    '''
    # Group admins can upgrade anybody.
    # The controller should handle the case where the target
    # is already a group admin.
    return canAdminGroup(person, group)

def canDowngradeUser(person, group, target):
    '''Check whether the user can downgrade target in the group

    :arg person: People object or username to check for permissions to upgrade
    :arg group: Group object to check whether `person` can downgrade within
    :returns: True if the user can downgrade target in the group else False
    '''
    # Group admins can downgrade anybody.
    return canAdminGroup(person, group)
