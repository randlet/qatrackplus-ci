
from django import forms
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import timedelta
from django.utils.translation import ugettext as _

from qatrack.parts import models as p_models
from qatrack.service_log import models as sl_models
from qatrack.units import models as u_models
from qatrack.service_log.forms import HoursMinDurationField


def max_24hr(value):
    if value > timedelta(hours=24):

        seconds = value.total_seconds()
        hours = seconds // 3600
        mins = (seconds % 3600) // 60

        raise ValidationError(
            _('Duration can not be greater than 24 hours')
        )


year_select = forms.ChoiceField(
    required=False,
    choices=[(y, y) for y in range(timezone.now().year - 20, timezone.now().year + 10)],
    initial=timezone.now().year
).widget.render('year_select', timezone.now().year, attrs={'id': 'id_year_select'})

month_select = forms.ChoiceField(
        required=False,
        choices=[
            (0, 'January'),
            (1, 'February'),
            (2, 'March'),
            (3, 'April'),
            (4, 'May'),
            (5, 'June'),
            (6, 'July'),
            (7, 'August'),
            (8, 'September'),
            (9, 'October'),
            (10, 'November'),
            (11, 'December'),
        ],
        initial=timezone.now().month - 1
    ).widget.render('month_select', timezone.now().month - 1, attrs={'id': 'id_month_select'})


class UnitAvailableTimeForm(forms.ModelForm):

    hours_sunday = HoursMinDurationField(
        help_text='Hours available on sundays (hh:mm)', label='Sunday', validators=[max_24hr]
    )
    hours_monday = HoursMinDurationField(
        help_text='Hours available on mondays (hh:mm)', label='Monday', validators=[max_24hr]
    )
    hours_tuesday = HoursMinDurationField(
        help_text='Hours available on tuesdays (hh:mm)', label='Tuesday', validators=[max_24hr]
    )
    hours_wednesday = HoursMinDurationField(
        help_text='Hours available on wednesdays (hh:mm)', label='Wednesday', validators=[max_24hr]
    )
    hours_thursday = HoursMinDurationField(
        help_text='Hours available on thursdays (hh:mm)', label='Thursday', validators=[max_24hr]
    )
    hours_friday = HoursMinDurationField(
        help_text='Hours available on fridays (hh:mm)', label='Friday', validators=[max_24hr]
    )
    hours_saturday = HoursMinDurationField(
        help_text='Hours available on saturdays (hh:mm)', label='Saturday', validators=[max_24hr]
    )

    unit = forms.ModelChoiceField(widget=forms.HiddenInput(), queryset=u_models.Unit.objects.all())

    class Meta:
        model = u_models.UnitAvailableTime
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(UnitAvailableTimeForm, self).__init__(*args, **kwargs)

        for f in self.fields:
            if f == 'date_changed':
                self.fields[f].widget.attrs['class'] = 'form-control vDateField'
                self.fields[f].input_formats = ['%d-%m-%Y', '%Y-%m-%d']
            elif f in ['year_select', 'month_select']:
                self.fields[f].widget.attrs['class'] = 'form-control'
            else:
                self.fields[f].widget.attrs['class'] = 'form-control duration weekday-duration'

        for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
            self.fields['hours_' + day].widget.attrs['placeholder'] = day

            if not self.instance.pk:
                self.fields['hours_' + day].initial = settings.DEFAULT_AVAILABLE_TIMES['hours_' + day]

    def clean_date_changed(self):
        date_changed = self.cleaned_data['date_changed']
        unit = self.cleaned_data.get('unit')
        if unit and date_changed < unit.date_acceptance:
            self.add_error('date_changed', 'Date changed cannot be before units acceptance date')
        return date_changed


class UnitAvailableTimeEditForm(forms.ModelForm):

    units = forms.ModelMultipleChoiceField(queryset=u_models.Unit.objects.all())
    hours = HoursMinDurationField(help_text='Hours available (hh:mm)', label='Hours', validators=[max_24hr])

    class Meta:
        model = u_models.UnitAvailableTimeEdit
        fields = ('date', 'hours', 'name', 'units')

    def __init__(self, *args, **kwargs):
        super(UnitAvailableTimeEditForm, self).__init__(*args, **kwargs)

        for f in self.fields:
            if f == 'date':
                self.fields[f].widget.attrs['class'] = 'form-control vDateField'
                self.fields[f].input_formats = ['%d-%m-%Y', '%Y-%m-%d']
            elif f == 'hours':
                self.fields[f].widget.attrs['class'] = 'form-control duration'
            elif f == 'units':
                self.fields[f].widget.attrs['id'] = 'id_edit_units'
            else:
                self.fields[f].widget.attrs['class'] = 'form-control'

    def clean_date(self):
        cleaned = self.cleaned_data['date']
        if cleaned < self.instance.unit.date_acceptance:
            raise ValidationError('Unit cannot have available time edit before it\'s date of acceptance.')
        return cleaned
