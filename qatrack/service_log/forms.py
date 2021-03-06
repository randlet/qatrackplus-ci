
from django import forms
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.conf import settings
from django.contrib.auth.models import User, Permission
from django.db.models import Field, ObjectDoesNotExist, Q, QuerySet
from django.utils import timezone
from django.utils.dateparse import parse_duration
from django.utils.encoding import force_text
from django.utils.translation import ugettext as _
from form_utils.forms import BetterModelForm

from qatrack.attachments.models import Attachment
from qatrack.service_log import models
from qatrack.qa import models as qa_models
from qatrack.units import models as u_models


def get_user_name(user):
    return user.username if not user.first_name or not user.last_name else '{} {}'.format(user.first_name, user.last_name)


def item_val_to_string(item):
    if item is None:
        return ''
    elif isinstance(item, str):
        return item
    elif isinstance(item, User):
        return get_user_name(item)
    elif isinstance(item, timezone.datetime):
        return timezone.localtime(item).strftime('%b %m, %I:%M %p')
    elif isinstance(item, timezone.timedelta):
        total_seconds = int(item.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return '{}:{:02}'.format(hours, minutes)
    elif isinstance(item, QuerySet):
        return ', '.join([str(i) for i in item])
    else:
        return str(item)


def duration_string_hours_mins(duration):

    seconds = int(duration.total_seconds())
    hours = seconds // 3600
    minutes = (seconds - hours * 3600) // 60

    if seconds > 0 and minutes < 1 and hours == 0:
        return '00:01'

    return '{:02d}:{:02d}'.format(hours, minutes)


class HoursMinDurationField(forms.DurationField):

    def __init__(self, *args, **kwargs):
        super(HoursMinDurationField, self).__init__(*args, **kwargs)
        self.widget.attrs.update({'class': 'inputmask'})

    def prepare_value(self, value):
        if isinstance(value, timezone.timedelta):
            return duration_string_hours_mins(value)
        return value

    def to_python(self, value):
        if value is not None:
            if value == '__:__':
                return None
            value = value.replace('_', '0').replace(':', '')
        if value in self.empty_values:
            return None
        if isinstance(value, timezone.timedelta):
            return value
        value = '{:04d}'.format(int(value))
        value = parse_duration(force_text(':'.join([value[:2], value[2:], '00'])))
        if value is None:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        return value


class UserModelChoiceField(forms.ModelChoiceField):

    title = ''

    def label_from_instance(self, user):
        return user.username if not user.first_name or not user.last_name else '{} {}'.format(user.first_name, user.last_name)


class HoursForm(forms.ModelForm):

    user_or_thirdparty = forms.ChoiceField(label='User or third party')
    time = HoursMinDurationField(help_text='hh:mm')

    class Meta:
        model = models.Hours
        fields = ('time', 'user_or_thirdparty')

    def __init__(self, *args, **kwargs):
        super(HoursForm, self).__init__(*args, **kwargs)

        choices = [('', '---------')]
        perm = Permission.objects.get(codename='can_have_hours')
        if self.instance.user:
            users = User.objects.filter(
                Q(groups__permissions=perm, is_active=True) |
                Q(user_permissions=perm, is_active=True) |
                Q(pk=self.instance.user.id)
            ).distinct().order_by('last_name')
        else:
            users = User.objects.filter(
                Q(groups__permissions=perm, is_active=True) |
                Q(user_permissions=perm, is_active=True)
            ).distinct().order_by('last_name')
        for user in users:
            name = user.username if not user.first_name or not user.last_name else '{} {}'.format(user.first_name, user.last_name)
            choices.append(('user-%s' % user.id, name))
        for tp in models.ThirdParty.objects.all():
            choices.append(('tp-%s' % tp.id, tp.get_full_name()))

        self.fields['user_or_thirdparty'].choices = choices

        self.fields['user_or_thirdparty'].widget.attrs.update({'class': 'select2 user_or_thirdparty'})
        time_classes = self.fields['time'].widget.attrs.get('class', '')
        time_classes += ' max-width-100 form-control user_thirdparty_time'
        self.fields['time'].widget.attrs.update({'class': time_classes, 'autocomplete': 'off'})

        if self.instance.user:
            self.initial['user_or_thirdparty'] = 'user-' + str(self.instance.user.id)
        elif self.instance.third_party:
            self.initial['user_or_thirdparty'] = 'tp-' + str(self.instance.third_party.id)

    def clean_user_or_thirdparty(self):

        obj_type, obj_id = self.cleaned_data['user_or_thirdparty'].split('-')

        for k1, v1 in self.data.items():
            if '-user_or_thirdparty' in k1 and v1 != '':
                for k2, v2 in self.data.items():
                    if '-user_or_thirdparty' in k2 and k2 != k1 and v1 == v2:
                        raise ValidationError('Duplicate hours user or third party')

        if obj_type == 'user':
            return User.objects.get(id=obj_id)
        elif obj_type == 'tp':
            return models.ThirdParty.objects.get(id=obj_id)

        raise ValidationError('Not a User or Third Party object.')


HoursFormset = forms.inlineformset_factory(models.ServiceEvent, models.Hours, form=HoursForm, extra=2)


class ReturnToServiceQAForm(forms.ModelForm):

    unit_test_collection = forms.ModelChoiceField(queryset=qa_models.UnitTestCollection.objects.none())
    test_list_instance = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    all_reviewed = forms.BooleanField(widget=forms.HiddenInput(), required=False)

    log_change_fields = (
        'unit_test_collection', 'test_list_instance'
    )

    class Meta:
        model = models.ReturnToServiceQA
        fields = ('unit_test_collection', 'test_list_instance', 'all_reviewed')

    def __init__(self, *args, **kwargs):
        self.service_event_instance = kwargs.pop('service_event_instance')
        self.unit_field = kwargs.pop('unit_field')
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if 'unit_field' in self.data and self.data['unit_field']:
            self.unit_field = u_models.Unit.objects.get(pk=self.data['unit_field'])

        if self.unit_field:
            uf_cache = cache.get('active_unit_test_collections_for_unit_%s' % self.unit_field.id, None)
            if not uf_cache:
                uf_cache = qa_models.UnitTestCollection.objects.filter(
                    unit=self.unit_field,
                    active=True
                ).order_by('name')
                cache.set('active_unit_test_collections_for_unit_%s' % self.unit_field.id, uf_cache)
            self.fields['unit_test_collection'].queryset = uf_cache

            self.fields['unit_test_collection'].widget.attrs.update({
                'disabled': not self.user.has_perm('service_log.add_returntoserviceqa')
            })
        else:
            self.fields['unit_test_collection'].widget.attrs.update({'disabled': True})

        if self.instance.test_list_instance:
            self.fields['unit_test_collection'].widget.attrs.update({'disabled': True})
            self.fields['unit_test_collection'].disabled = True
            self.initial['test_list_instance'] = self.instance.test_list_instance.id
            self.initial['all_reviewed'] = int(self.instance.test_list_instance.all_reviewed)
        else:
            self.initial['all_reviewed'] = 0

        self.fields['unit_test_collection'].widget.attrs.update({
            'class': 'rtsqa-utc select2', 'data-prefix': self.prefix,
            'oldvalue': self.initial.get('unit_test_collection', '')
        })
        self.fields['test_list_instance'].widget.attrs.update({'class': 'tli-instance', 'data-prefix': self.prefix})
        self.fields['all_reviewed'].widget.attrs.update({'class': 'tli-all-reviewed'})


    def clean_unit_test_collection(self):
        utc = self.cleaned_data['unit_test_collection']
        return utc

    def clean_test_list_instance(self):
        tli_id = self.cleaned_data['test_list_instance']
        if tli_id is not None:
            return qa_models.TestListInstance.objects.get(pk=tli_id)
        return None


# ReturnToServiceQAFormset = forms.inlineformset_factory(models.ServiceEvent, models.ReturnToServiceQA, form=ReturnToServiceQAForm, extra=0)
def get_rtsqa_formset(extra):
    return forms.inlineformset_factory(models.ServiceEvent, models.ReturnToServiceQA, form=ReturnToServiceQAForm, extra=extra)


class ServiceEventMultipleField(forms.ModelMultipleChoiceField):

    def clean(self, value):

        key = self.to_field_name or 'pk'
        # deduplicate given values to avoid creating many querysets or
        # requiring the database backend deduplicate efficiently.
        try:
            value = frozenset(value)
        except TypeError:
            # list of lists isn't hashable, for example
            raise ValidationError(
                self.error_messages['list'],
                code='list',
            )
        for pk in value:
            try:
                self.queryset.filter(**{key: pk})
            except (ValueError, TypeError):
                raise ValidationError(
                    self.error_messages['invalid_pk_value'],
                    code='invalid_pk_value',
                    params={'pk': pk},
                )
        qs = models.ServiceEvent.objects.filter(**{'%s__in' % key: value})
        pks = set(force_text(getattr(o, key)) for o in qs)
        for val in value:
            if force_text(val) not in pks:
                raise ValidationError(
                    self.error_messages['invalid_choice'],
                    code='invalid_choice',
                    params={'value': val},
                )
        return qs


class SelectWithDisabledWidget(forms.Select):

    option_template_name = 'service_log/service_event_select_widget_option.html'

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):

        to_return = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        title_html = ''
        disabled = False

        if isinstance(label, dict):
            disabled = dict.get(label, 'disabled')
            title_html = ' title="%s"' % dict.get(label, 'title') if dict.get(label, 'title') else ''
            label = label['label']

        # to_return['selected'] = selected
        to_return['disabled'] = disabled
        to_return['title_html'] = title_html
        to_return['label'] = label
        return to_return


class TLIInitiatedField(forms.ModelChoiceField):

    label = ''
    required = False
    widget = forms.HiddenInput()

    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            tli = qa_models.TestListInstance.objects.get(pk=value)
        except (ValueError, TypeError, qa_models.TestListInstance.DoesNotExist) as e:
            raise ValidationError(self.error_messages['invalid_choice'], code='invalid_choice')
        return tli

    def _coerce(self, data):
        if isinstance(data, str):
            return int(data)
        elif isinstance(data, qa_models.TestListInstance):
            return data.id
        else:
            return data


class ModelSelectWithOptionTitles(forms.Select):

    option_inherits_attrs = True

    def __init__(self, attrs=None, choices=(), model=None, title_variable=None):
        super().__init__(attrs=attrs, choices=choices)
        self.model = model
        self.title_variable = title_variable

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        if value in [None, '']:
            title = '-----'
        elif self.title_variable is not None and self.model is not None:
            title = getattr(self.model.objects.get(pk=value), self.title_variable)
        else:
            title = ''
        if attrs is None:
            attrs = {'title': title}
        else:
            attrs.update({'title': title})
        option = super().create_option(name, value, label, selected, index, subindex=None, attrs=attrs)
        return option


class ServiceEventForm(BetterModelForm):

    serviceable_units = models.Unit.objects.filter(is_serviceable=True)
    unit_field_fake = forms.ModelChoiceField(queryset=serviceable_units, label='Unit', required=False)
    unit_field = forms.ModelChoiceField(queryset=models.Unit.objects.all())
    service_area_field = forms.ModelChoiceField(
        queryset=models.ServiceArea.objects.all(), label='Service area'
    )
    duration_service_time = HoursMinDurationField(
        label=_('Service time'), required=False,
        help_text=models.ServiceEvent._meta.get_field('duration_service_time').help_text
    )
    duration_lost_time = HoursMinDurationField(
        label=_('Lost time'), required=False,
        help_text=models.ServiceEvent._meta.get_field('duration_lost_time').help_text
    )
    service_event_related_field = ServiceEventMultipleField(
        required=False, queryset=models.ServiceEvent.objects.none(), label=_('Related Service Events'),
        help_text=models.ServiceEvent._meta.get_field('service_event_related').help_text
    )
    is_review_required = forms.BooleanField(required=False, label=_('Review required'))
    is_review_required_fake = forms.BooleanField(
        required=False, widget=forms.CheckboxInput(), label=_('Review required'), initial=True,
        help_text=models.ServiceEvent._meta.get_field('is_review_required').help_text
    )

    test_list_instance_initiated_by = TLIInitiatedField(
        required=False, label=_('Initiated By'), queryset=qa_models.TestListInstance.objects.none()
    )

    initiated_utc_field = forms.ModelChoiceField(
        required=False, queryset=qa_models.UnitTestCollection.objects.none(), label='Initiated By',
        help_text=_('Was there a QA session that initiated this service event?')
    )
    service_type = forms.ModelChoiceField(
        queryset=models.ServiceType.objects.filter(is_active=True), label=_('Service type'),
        widget=ModelSelectWithOptionTitles(model=models.ServiceType, title_variable='description')
    )
    service_status = forms.ModelChoiceField(
        help_text=models.ServiceEvent._meta.get_field('service_status').help_text,
        queryset=models.ServiceEventStatus.objects.none()
    )
    qafollowup_comments = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}), required=False, label=_('Add Comment'),
        help_text=_('Comments related to return to service')
    )

    se_attachments = forms.FileField(
        label="Attachments",
        max_length=150,
        required=False,
        widget=forms.FileInput(attrs={
            'multiple': '',
            'class': 'file-upload',
            'style': 'display:none',
        })
    )
    se_attachments_delete_ids = forms.CharField(widget=forms.HiddenInput(), required=False)

    log_change_fields = (
        'test_list_instance_initiated_by', 'is_review_required', 'datetime_service', 'service_area_field',
        'service_type', 'service_event_related_field', 'problem_description', 'safety_precautions',
        'work_description', 'duration_service_time', 'duration_lost_time'
    )

    class Meta:

        model = models.ServiceEvent
        fieldsets = [
            ('hidden_fields', {
                'fields': ['test_list_instance_initiated_by', 'is_review_required', 'unit_field'],
            }),
            ('service_status', {
               'fields': [
                   'service_status'
               ],
            }),
            ('left_fields', {
                'fields': [
                    'datetime_service', 'unit_field_fake', 'service_area_field', 'service_type', 'is_review_required_fake',
                ],
            }),
            ('right_fields', {
                'fields': [
                    'service_event_related_field', 'initiated_utc_field',
                ],
            }),
            ('problem_and_safety', {
                'fields': [
                    'problem_description', 'safety_precautions',
                ]
            }),
            ('work_description', {
                'fields': [
                    'work_description'
                ]
            }),
            ('time_fields', {
                'fields': ['duration_service_time', 'duration_lost_time'],
            }),
            ('qafollowup_comments', {
                'fields': ['qafollowup_comments'],
            })
        ]

    def __init__(self, *args, **kwargs):
        self.initial_ib = kwargs.pop('initial_ib', None)
        self.initial_u = kwargs.pop('initial_u', None)
        self.group_linkers = kwargs.pop('group_linkers', [])
        self.user = kwargs.pop('user', None)
        super(ServiceEventForm, self).__init__(*args, **kwargs)

        is_new = self.instance.id is None
        is_bound = self.is_bound

        g_fields = []
        self.g_link_dict = {}
        for g_link in self.group_linkers:
            field_name = 'group_linker_%s' % g_link.id

            self.g_link_dict[field_name] = {
                'g_link': g_link,
            }
            # if not is_new:
            try:
                g_link_instance = models.GroupLinkerInstance.objects.get(
                    group_linker=g_link, service_event=self.instance
                )
                self.initial[field_name] = g_link_instance.user
                queryset = User.objects.filter(
                    Q(groups=g_link.group, is_active=True) | Q(pk=g_link_instance.user.id)
                ).distinct().order_by('last_name')
            except ObjectDoesNotExist:
                queryset = User.objects.filter(groups=g_link.group, is_active=True).order_by('last_name')

            self.fields[field_name] = UserModelChoiceField(
                queryset=queryset, help_text=g_link.help_text, label=g_link.name, required=False
            )
            self.fields[field_name].widget.attrs.update({'class': 'select2'})
            self.fields[field_name].title = g_link.description

            g_fields.append(field_name)
        self._fieldsets.append(('g_link_fields', {'fields': g_fields}))

        # If this is a new ServiceEvent
        if is_new:

            # if url param 'ib' is included. For prefilling initiated by field
            if self.initial_ib and 'test_list_instance_initiated_by' not in self.data:
                initial_ib_tli = qa_models.TestListInstance.objects.get(id=self.initial_ib)
                self.initial['test_list_instance_initiated_by'] = initial_ib_tli
                initial_ib_utc = initial_ib_tli.unit_test_collection
                initial_ib_utc_u = initial_ib_utc.unit
                self.initial['unit_field'] = initial_ib_utc_u
                self.initial['initiated_utc_field'] = initial_ib_utc
                self.fields['service_area_field'].queryset = models.ServiceArea.objects.filter(units=initial_ib_utc_u)
                i_utc_f_qs = qa_models.UnitTestCollection.objects.filter(unit=initial_ib_utc_u, active=True).order_by('name')
                choices = (('', '---------'),) + tuple(
                    ((utc.id, '(%s) %s' % (utc.frequency if utc.frequency else 'Ad Hoc', utc.name)) for utc in i_utc_f_qs)
                )
                self.fields['initiated_utc_field'].choices = choices

            if self.initial_u and 'unit_field' not in self.data:
                try:
                    initial_unit = u_models.Unit.objects.get(pk=self.initial_u)
                    self.initial['unit_field'] = initial_unit
                    self.fields['service_area_field'].queryset = models.ServiceArea.objects.filter(units=initial_unit)
                    i_utc_f_qs = qa_models.UnitTestCollection.objects.filter(
                        unit=initial_unit, active=True
                    ).order_by('name')
                    self.fields['initiated_utc_field'].choices = (('', '---------'),) + tuple(
                        ((utc.id, '(%s) %s' % (utc.frequency if utc.frequency else 'Ad Hoc', utc.name)) for utc in i_utc_f_qs)
                    )
                except ObjectDoesNotExist:
                    pass

            if 'service_event_related_field' in self.data:
                self.fields['service_event_related_field'].queryset = models.ServiceEvent.objects.filter(
                    pk__in=self.data.getlist('service_event_related_field')
                )

            if 'unit_field' not in self.data and 'unit_field' not in self.initial:
                self.fields['service_area_field'].widget.attrs.update({'disabled': True})
                self.fields['service_event_related_field'].widget.attrs.update({'disabled': True})
                self.fields['initiated_utc_field'].widget.attrs.update({'disabled': True})

            if 'unit_field' in self.data:
                if self.data['unit_field']:
                    self.fields['service_area_field'].queryset = models.ServiceArea.objects.filter(
                        units=self.data['unit_field']
                    )
                    self.fields['initiated_utc_field'].queryset = qa_models.UnitTestCollection.objects.filter(
                        unit=self.data['unit_field']
                    )
                else:
                    self.fields['service_area_field'].widget.attrs.update({'disabled': True})
                    self.fields['service_event_related_field'].widget.attrs.update({'disabled': True})
                    self.fields['initiated_utc_field'].widget.attrs.update({'disabled': True})

            if self.user.has_perm('service_log.review_serviceevent'):
                self.fields['service_status'].queryset = models.ServiceEventStatus.objects.all()
            else:
                self.fields['service_status'].queryset = models.ServiceEventStatus.objects.filter(
                    is_review_required=True
                )

            # some data wasn't attempted to be submitted already
            if not is_bound:
                self.initial['service_status'] = models.ServiceEventStatus.get_default()

        # if we are editing a saved instance
        else:

            try:
                unit = u_models.Unit.objects.get(pk=self.data['unit_field'])
            except (ObjectDoesNotExist, ValueError, KeyError):
                unit = self.instance.unit_service_area.unit

            self.fields['unit_field_fake'].queryset = self.serviceable_units | models.Unit.objects.filter(pk=unit.id)
            self.initial['unit_field'] = unit
            self.initial['service_area_field'] = self.instance.unit_service_area.service_area
            self.initial['service_event_related_field'] = self.instance.service_event_related.all()
            self.fields['service_event_related_field'].queryset = self.initial['service_event_related_field']
            self.fields['service_area_field'].queryset = models.ServiceArea.objects.filter(units=unit)

            # disable Unit field if service event has initiated by or any existing RTSQA
            rtsqa_exisits = models.ReturnToServiceQA.objects.filter(service_event=self.instance).exists()
            if self.instance.test_list_instance_initiated_by or rtsqa_exisits:
                self.fields['unit_field_fake'].widget.attrs.update({
                   'title': 'Cannot change Unit once "Initiated By" or any "RTS QA" have been added',
                })

            if self.instance.service_type.is_review_required:
                self.fields['is_review_required_fake'].widget.attrs.update({'disabled': True})

            self.initial['is_review_required_fake'] = self.instance.is_review_required

            if self.user.has_perm('service_log.review_serviceevent'):
                self.fields['service_status'].queryset = models.ServiceEventStatus.objects.all()
            else:
                self.fields['service_status'].queryset = models.ServiceEventStatus.objects.filter(
                    Q(is_review_required=True) | Q(pk=self.instance.service_status.id)
                )

            if self.instance.test_list_instance_initiated_by:
                self.initial['initiated_utc_field'] = self.instance.test_list_instance_initiated_by.unit_test_collection
                self.initial['test_list_instance_initiated_by'] = self.instance.test_list_instance_initiated_by

            i_utc_f_qs = qa_models.UnitTestCollection.objects.select_related('frequency').filter(
                unit=unit, active=True
            ).order_by('name')
            self.fields['initiated_utc_field'].choices = (('', '---------'),) + tuple(
                ((utc.id, '(%s) %s' % (utc.frequency if utc.frequency else 'Ad Hoc', utc.name)) for utc in i_utc_f_qs)
            )
            if not self.instance.service_type.is_active:
                self.fields['service_type'].queryset |= models.ServiceType.objects.filter(id=self.instance.service_type.id)

        for f in ['safety_precautions', 'problem_description', 'work_description', 'qafollowup_comments']:
            self.fields[f].widget.attrs.update({'rows': 3, 'class': 'autosize'})

        select2_fields = [
            'unit_field_fake', 'service_area_field', 'service_type', 'service_status',
            'initiated_utc_field'
        ]
        for f in select2_fields:
            self.fields[f].widget.attrs['class'] = 'select2'

        for f in ['datetime_service']:
            self.fields[f].widget.attrs['class'] = 'daterangepicker-input'
            self.fields[f].widget.format = settings.INPUT_DATE_FORMATS[0]
            self.fields[f].input_formats = settings.INPUT_DATE_FORMATS
            self.fields[f].widget.attrs['title'] = settings.DATETIME_HELP
            # self.fields[f].help_text = settings.DATETIME_HELP

        for f in ['duration_service_time', 'duration_lost_time']:
            classes = self.fields[f].widget.attrs.get('class', '')
            classes += ' max-width-100'
            self.fields[f].widget.attrs.update({'class': classes, 'autocomplete': 'off'})

        for f in self.fields:
            classes = self.fields[f].widget.attrs.get('class', '')
            classes += ' form-control'
            self.fields[f].widget.attrs.update({'class': classes, 'autocomplete': 'off'})

        for f in ['is_review_required_fake', 'is_review_required']:
            classes = self.fields[f].widget.attrs.get('class', '')
            classes = classes.replace('form-control', '')
            self.fields[f].widget.attrs.update({'class': classes})

        self.fields['problem_description'].widget.attrs['placeholder'] = 'required'
        self.fields['initiated_utc_field'].widget.attrs.update({'data-link': reverse('tli_select')})

    def strigify_form_item(self, item):

        new = self.cleaned_data.get(item)
        old = self.initial.get(item)

        if item == 'test_list_instance_initiated_by':
            if new is not None:
                new = new.str_verbose()
            if old is not None:
                old = old.str_verbose()
        elif isinstance(old, int) and issubclass(type(self.fields.get(item)), forms.ModelChoiceField):
            old = self.fields[item].queryset.model.objects.get(pk=old)

        new = item_val_to_string(new)
        old = item_val_to_string(old)
        name = self.fields[item].label

        return name, new, old

    def stringify_form_changes(self, request):

        form_strings = {}
        for ch in self.changed_data:
            if ch in self.log_change_fields or 'group_linker' in ch:
                name, new, old = self.strigify_form_item(ch)
                form_strings[name] = {'new': new, 'old': old}

        if 'se_attachments' in self.changed_data:

            added_a = []
            for idx, f in enumerate(request.FILES.getlist('se_attachments')):
                added_a.append(str(f))
            form_strings['a_added'] = {'new': added_a, 'old': ''}

        a_delete_ids = self.cleaned_data.get('se_attachments_delete_ids').split(',')
        if a_delete_ids != ['']:
            attachments = Attachment.objects.filter(id__in=a_delete_ids)
            deleted_a = []
            for a in attachments:
                deleted_a.append(a.label)
            form_strings['a_deleted'] = {'new': '', 'old': deleted_a}

        return form_strings

    def stringify_status_change(self):
        name, new, old = self.strigify_form_item('service_status')
        return {'new': new, 'old': old}

    def save(self, *args, **kwargs):
        unit = self.cleaned_data.get('unit_field')
        service_area = self.cleaned_data.get('service_area_field')
        usa = models.UnitServiceArea.objects.get(unit=unit, service_area=service_area)

        if self.cleaned_data['service_type'].is_review_required:
            self.instance.is_review_required = True

        self.instance.unit_service_area = usa
        super(ServiceEventForm, self).save(*args, **kwargs)

        return self.instance

    def clean(self):
        super(ServiceEventForm, self).clean()

        if not self.cleaned_data.get('unit_field'):
            self.add_error('unit_field_fake', ValidationError('This field is required'))

        if 'initiated_utc_field' in self._errors:
            del self._errors['initiated_utc_field']

        # Check for incomplete and unreviewed RTS QA if status.rts_qa_must_be_reviewed = True
        if 'service_status' not in self.cleaned_data:
            raise ValidationError(_('This field is required.'), code='required')
        if self.cleaned_data['service_status'].rts_qa_must_be_reviewed:
            raize = False
            for k, v in self.data.items():
                if k.startswith('rtsqa-') and k.endswith('-id'):
                    prefix = k.replace('-id', '')

                    if prefix + '-unit_test_collection' in self.data and self.data[prefix + '-unit_test_collection'] != '':
                        if prefix + '-DELETE' not in self.data or self.data[prefix + '-DELETE'] != 'on':
                            if self.data[prefix + '-test_list_instance'] == '':
                                raize = True
                                break
                    tli_id = self.data[prefix + '-test_list_instance']
                    if tli_id != '' and not qa_models.TestListInstance.objects.get(pk=tli_id).all_reviewed:
                        if prefix + '-DELETE' not in self.data or self.data[prefix + '-DELETE'] != 'on':
                            raize = True
                            break

            if raize:
                self._errors['service_status'] = ValidationError(
                    'Cannot select status: Return to service qa must be performed and reviewed.'
                )

        # If unit field was disabled due to initiated by or rtsqa existing for already saved service event,
        #   add the initial unit back to cleaned data since django tries to set it to None and unit is of course requried.
        if self.instance.pk and ('unit_field' not in self.cleaned_data or self.cleaned_data['unit_field'] is None):
            self.cleaned_data['unit_field'] = self.instance.unit_service_area.unit

        return self.cleaned_data

    def clean_unit_field_fake(self):
        return self.cleaned_data.get('unit_field')


class ServiceEventDeleteForm(forms.ModelForm):

    reason = forms.ChoiceField(choices=settings.DELETE_REASONS)
    comment = forms.CharField(max_length=255, widget=forms.Textarea(), required=False)

    class Meta:

        model = models.ServiceEvent
        fields = ('id',)

    def __init__(self, *args, **kwargs):
        pk = kwargs.pop('pk', None)
        super().__init__(*args, **kwargs)

        self.fields['comment'].widget.attrs.update({'rows': 3, 'class': 'autosize form-control'})
        self.fields['reason'].widget.attrs.update({'class': 'form-control'})
