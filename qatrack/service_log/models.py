import json
import re

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.db.utils import IntegrityError
from django.utils import timezone
from django.utils.translation import ugettext as _

from qatrack.qa.models import TestListInstance, UnitTestCollection
from qatrack.units.models import NameNaturalKeyManager, Unit, Vendor

re_255 = '([0-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-5])'
color_re = re.compile('^rgba\(' + re_255 + ',' + re_255 + ',' + re_255 + ',(0(\.[0-9][0-9]?)?|1)\)$')
validate_color = RegexValidator(color_re, _('Enter a valid color.'), 'invalid')

NEW_SERVICE_EVENT = 'new_se'
MODIFIED_SERVICE_EVENT = 'mod_se'
STATUS_SERVICE_EVENT = 'stat_se'
CHANGED_RTSQA = 'rtsqa'
PERFORMED_RTS = 'perf_rts'
APPROVED_RTS = 'app_rts'
DELETED_SERVICE_EVENT = 'del_se'

LOG_TYPES = (
    (NEW_SERVICE_EVENT, 'New Service Event'),
    (MODIFIED_SERVICE_EVENT, 'Modified Servicew Event'),
    (STATUS_SERVICE_EVENT, 'Service Event Status Changed'),
    (CHANGED_RTSQA, 'Changed Return To Service'),
    (PERFORMED_RTS, 'Performed Return To Service'),
    (APPROVED_RTS, 'Approved Return To Service'),
    (DELETED_SERVICE_EVENT, 'Deleted Service Event')
)


class ServiceArea(models.Model):

    name = models.CharField(max_length=32, unique=True, help_text=_('Enter a short name for this service area'))
    units = models.ManyToManyField(Unit, through='UnitServiceArea', related_name='service_areas')

    objects = NameNaturalKeyManager()

    def natural_key(self):
        return (self.name,)

    def __str__(self):
        return self.name


class UnitServiceArea(models.Model):

    unit = models.ForeignKey(Unit, on_delete=models.CASCADE)
    service_area = models.ForeignKey(ServiceArea, on_delete=models.CASCADE)

    notes = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name_plural = _('Unit Service Area Memberships')
        unique_together = ('unit', 'service_area',)
        ordering = ('unit', 'service_area')

    def __str__(self):
        return '%s :: %s' % (self.unit.name, self.service_area.name)


class ServiceType(models.Model):

    name = models.CharField(max_length=32, unique=True, help_text=_('Enter a short name for this service type'))
    is_review_required = models.BooleanField(default=True, help_text=_('Does this service type require review'))
    is_active = models.BooleanField(default=True, help_text=_('Set to false if service type is no longer used'))
    description = models.TextField(
        max_length=512, help_text=_('Give a brief description of this service type'), null=True, blank=True
    )

    objects = NameNaturalKeyManager()

    def natural_key(self):
        return (self.name,)

    def __str__(self):
        return self.name


class ServiceEventStatus(models.Model):

    name = models.CharField(max_length=32, unique=True, help_text=_('Enter a short name for this service status'))
    is_default = models.BooleanField(
        default=False,
        help_text=_(
            'Is this the default status for all service events? If set to true every other service event '
            'status will be set to false'
        )
    )
    is_review_required = models.BooleanField(
        default=True, help_text=_('Do service events with this status require review?')
    )
    rts_qa_must_be_reviewed = models.BooleanField(
        default=True,
        verbose_name=_("Return To Service (RTS) QA Must be Reviewed"),
        help_text=_(
            'Service events with Return To Service (RTS) QA that has not been reviewed '
            'can not have this status selected if set to true.'
        ),
    )
    description = models.TextField(
        max_length=512, help_text=_('Give a brief description of this service event status'), null=True, blank=True
    )
    colour = models.CharField(default=settings.DEFAULT_COLOURS[0], max_length=22, validators=[validate_color])

    objects = NameNaturalKeyManager()

    class Meta:
        verbose_name_plural = _('Service event statuses')

    def save(self, *args, **kwargs):
        if self.is_default:
            try:
                temp = ServiceEventStatus.objects.get(is_default=True)
                if self != temp:
                    temp.is_default = False
                    temp.save()
            except ServiceEventStatus.DoesNotExist:
                pass
        super(ServiceEventStatus, self).save(*args, **kwargs)

    def natural_key(self):
        return (self.name,)

    def __str__(self):
        return self.name

    @staticmethod
    def get_default():
        try:
            default = ServiceEventStatus.objects.get(is_default=True)
        except ServiceEventStatus.DoesNotExist:
            return None
        return default

    @staticmethod
    def get_colour_dict():
        return {ses.id: ses.colour for ses in ServiceEventStatus.objects.all()}


class ServiceEventManager(models.Manager):

    def get_queryset(self, *args, **kwargs):
        return super().get_queryset(*args, **kwargs).filter(is_active=True)

    def get_deleted(self):
        return super().get_queryset().filter(is_active=False)


class ServiceEvent(models.Model):

    unit_service_area = models.ForeignKey(UnitServiceArea, on_delete=models.PROTECT)
    service_type = models.ForeignKey(ServiceType, on_delete=models.PROTECT)
    service_event_related = models.ManyToManyField(
        'self', symmetrical=True, blank=True, verbose_name=_('Related service events'),
        help_text=_('Enter the service event IDs of any related service events.')
    )
    service_status = models.ForeignKey(ServiceEventStatus, verbose_name=_('Status'), on_delete=models.PROTECT)

    user_status_changed_by = models.ForeignKey(User, null=True, blank=True, related_name='+', on_delete=models.PROTECT)
    user_created_by = models.ForeignKey(User, related_name='+', on_delete=models.PROTECT)
    user_modified_by = models.ForeignKey(User, null=True, blank=True, related_name='+', on_delete=models.PROTECT)
    test_list_instance_initiated_by = models.ForeignKey(
        TestListInstance,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='serviceevents_initiated'
    )

    datetime_status_changed = models.DateTimeField(null=True, blank=True)
    datetime_created = models.DateTimeField()
    datetime_service = models.DateTimeField(
        verbose_name=_('Date and time'), help_text=_('Date and time service performed')
    )
    datetime_modified = models.DateTimeField(null=True, blank=True)

    safety_precautions = models.TextField(
        null=True, blank=True, help_text=_('Describe any safety precautions taken')
    )
    problem_description = models.TextField(help_text=_('Describe the problem leading to this service event'))
    work_description = models.TextField(
        null=True, blank=True, help_text=_('Describe the work done during this service event')
    )
    duration_service_time = models.DurationField(
        verbose_name=_('Service time'), null=True, blank=True,
        help_text=_('Enter the total time duration of this service event (Hours : minutes)')
    )
    duration_lost_time = models.DurationField(
        verbose_name=_('Lost time'), null=True, blank=True,
        help_text=_('Enter the total clinical time lost for this service event (Hours : minutes)')
    )
    is_review_required = models.BooleanField(
        default=True, blank=True
    )
    is_active = models.BooleanField(default=True, blank=True)

    objects = ServiceEventManager()

    class Meta:
        get_latest_by = "datetime_service"

        permissions = (
            ('review_serviceevent', 'Can review service event'),
            ('view_serviceevent', 'Can view service event'),
        )

        ordering = ["-datetime_service"]

    def __str__(self):
        return str(self.id)

    def create_rts_log_details(self):
        rts_states = []
        for r in self.returntoserviceqa_set.all():

            utc = r.unit_test_collection
            if not r.test_list_instance:
                state = 'tli_incomplete'
                details = utc.name
            elif not r.test_list_instance.all_reviewed:
                state = 'tli_req_review'
                details = r.test_list_instance.test_list.name
            else:
                state = 'tli_reviewed'
                details = r.test_list_instance.test_list.name

            rts_states.append({'state': state, 'details': details})
        return rts_states

    def set_inactive(self):
        self.is_active = False
        self.save()

        parts_used = self.partused_set.all()
        for pu in parts_used:
            pu.add_back_to_storage()

    def set_active(self):
        self.is_active = True
        self.save()

        parts_used = self.partused_set.all()
        for pu in parts_used:
            pu.remove_from_storage()


class ThirdPartyManager(models.Manager):

    def get_queryset(self):
        return super(ThirdPartyManager, self).get_queryset().select_related('vendor')


class ThirdParty(models.Model):

    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT)

    first_name = models.CharField(max_length=32, help_text=_('Enter this person\'s first name'))
    last_name = models.CharField(max_length=32, help_text=_('Enter this person\'s last name'))

    objects = ThirdPartyManager()

    class Meta:
        verbose_name = _('Third party')
        verbose_name_plural = _('Third parties')
        unique_together = ('first_name', 'last_name', 'vendor')

    def __str__(self):
        return self.last_name + ', ' + self.first_name + ' (' + self.vendor.name + ')'

    def get_full_name(self):
        return str(self)


class Hours(models.Model):

    service_event = models.ForeignKey(ServiceEvent, on_delete=models.CASCADE)
    third_party = models.ForeignKey(ThirdParty, null=True, blank=True, on_delete=models.PROTECT)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT)

    time = models.DurationField(help_text=_('The time this person spent on this service event'))

    class Meta:
        verbose_name_plural = _("Hours")
        unique_together = ('service_event', 'third_party', 'user',)

        default_permissions = ()
        permissions = (
            ("can_have_hours", "Can have hours"),
        )

    def user_or_thirdparty(self):
        return self.user or self.third_party


class ReturnToServiceQAManager(models.Manager):

    def get_queryset(self, *args, **kwargs):
        return super().get_queryset(*args, **kwargs).filter(service_event__is_active=True)


class ReturnToServiceQA(models.Model):

    unit_test_collection = models.ForeignKey(
        UnitTestCollection, help_text=_('Select a TestList to perform'), on_delete=models.CASCADE
    )
    test_list_instance = models.ForeignKey(
        TestListInstance, null=True, blank=True, on_delete=models.SET_NULL, related_name='rtsqa_for_tli'
    )
    user_assigned_by = models.ForeignKey(User, related_name='+', on_delete=models.PROTECT)
    service_event = models.ForeignKey(ServiceEvent, on_delete=models.CASCADE)

    datetime_assigned = models.DateTimeField()

    objects = ReturnToServiceQAManager()

    class Meta:
        permissions = (
            ('view_returntoserviceqa', 'Can view return to service qa'),
            ('perform_returntoserviceqa', 'Can perform return to service qa')
        )
        ordering = ['-datetime_assigned']


class GroupLinker(models.Model):

    group = models.ForeignKey(Group, help_text=_('Select the group.'), on_delete=models.CASCADE)

    name = models.CharField(
        max_length=64, help_text=_('Enter this group\'s display name (ie: "Physicist reported to")')
    )
    description = models.TextField(
        null=True, blank=True, help_text=_('Describe the relationship between this group and service events.')
    )
    help_text = models.CharField(
        max_length=64, null=True, blank=True,
        help_text=_('Message to display when selecting user in service event form.')
    )

    class Meta:
        unique_together = ('name', 'group')

    def __str__(self):
        return self.name


class GroupLinkerInstance(models.Model):

    group_linker = models.ForeignKey(GroupLinker, on_delete=models.PROTECT)
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    service_event = models.ForeignKey(ServiceEvent, on_delete=models.CASCADE)

    datetime_linked = models.DateTimeField()

    class Meta:
        default_permissions = ()
        unique_together = ('service_event', 'group_linker')


class JSONField(models.TextField):

    def to_python(self, value):
        if value == "":
            return None

        try:
            if isinstance(value, str):
                return json.loads(value)
        except ValueError:
            pass
        return value

    def from_db_value(self, value, *args):
        return self.to_python(value)

    def get_db_prep_save(self, value, *args, **kwargs):
        if value == "":
            return None
        if isinstance(value, dict):
            value = json.dumps(value, cls=DjangoJSONEncoder)
        return value


class ServiceLogManager(models.Manager):

    def log_new_service_event(self, user, instance):
        self.create(
            user=user,
            service_event=instance,
            log_type=NEW_SERVICE_EVENT,
            datetime=timezone.now() - timezone.timedelta(seconds=1)  # Cheat to always show create logs before rtsqa logs created at same time
        )

    def log_changed_service_event(self, user, instance, extra_info):
        self.create(
            user=user,
            service_event=instance,
            log_type=MODIFIED_SERVICE_EVENT,
            extra_info=json.dumps(extra_info)
        )

    def log_service_event_status(self, user, instance, extra_info, status_change):

        self.create(
            user=user,
            service_event=instance,
            log_type=STATUS_SERVICE_EVENT,
            extra_info=json.dumps({'status_change': status_change, 'other_changes': extra_info})
        )

    def log_rtsqa_changes(self, user, instance):

        self.create(
            user=user,
            service_event=instance,
            log_type=CHANGED_RTSQA,
            extra_info=json.dumps(instance.create_rts_log_details())
        )

    def log_service_event_delete(self, user, instance, extra_info):

        self.create(
            user=user,
            service_event=instance,
            log_type=DELETED_SERVICE_EVENT,
            extra_info=json.dumps(extra_info)
        )


class ServiceLog(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    service_event = models.ForeignKey(ServiceEvent, on_delete=models.CASCADE)

    log_type = models.CharField(choices=LOG_TYPES, max_length=10)

    extra_info = JSONField(blank=True, null=True)
    datetime = models.DateTimeField(default=timezone.now, editable=False)

    objects = ServiceLogManager()

    class Meta:
        ordering = ('-datetime',)
        default_permissions = ()


@receiver(pre_save, sender=Hours, dispatch_uid="qatrack.service_log.models.ensure_hours_unique")
def ensure_hours_unique(sender, instance, raw, using, update_fields, **kwargs):
    """Some DB's don't consider multiple rows which contain the same columns
    and include null to violate unique contraints so we do our own check"""

    if instance.id is None:
        try:
            Hours.objects.get(service_event=instance.service_event, third_party=instance.third_party, user=instance.user)
        except Hours.DoesNotExist:
            pass
        else:
            # not a unique Hours object
            raise IntegrityError
