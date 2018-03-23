
from django import forms
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.db.models import ObjectDoesNotExist, Q
from django.utils.encoding import force_text
from form_utils.forms import BetterModelForm

from qatrack.parts import models as p_models
from qatrack.service_log import models as sl_models
from qatrack.units import models as u_models


class PartChoiceField(forms.ModelChoiceField):

    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            part = p_models.Part.objects.get(pk=value)
        except (ValueError, TypeError, p_models.Part.DoesNotExist) as e:
            raise ValidationError(self.error_messages['invalid_choice'], code='invalid_choice')
        return part


class FromStorageField(forms.ModelChoiceField):

    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            storage = p_models.Storage.objects.get(pk=value)
        except (ValueError, TypeError, p_models.Part.DoesNotExist) as e:
            raise ValidationError(self.error_messages['invalid_choice'], code='invalid_choice')
        return storage


class PartUsedForm(forms.ModelForm):

    from_storage = FromStorageField(
        required=False,
        queryset=p_models.Storage.objects.none()
    )
    part = PartChoiceField(
        queryset=p_models.Part.objects.none(),
        help_text=p_models.PartUsed._meta.get_field('part').help_text
    )

    class Meta:
        model = p_models.PartUsed
        fields = ('part', 'from_storage', 'quantity')

    def __init__(self, *args, **kwargs):
        super(PartUsedForm, self).__init__(*args, **kwargs)

        is_new = self.instance.id is None

        if is_new:

            if '%s-part' % self.prefix in self.data and self.data.get('%s-part' % self.prefix):
                self.fields['part'].queryset = p_models.Part.objects.filter(pk=self.data.get('%s-part' % self.prefix))
                if '%s-from_storage' % self.prefix in self.data and self.data.get('%s-from_storage' % self.prefix):
                    self.fields['from_storage'].queryset = p_models.PartStorageCollection.objects.filter(
                        part=self.data.get('%s-part' % self.prefix)
                    )
                    s_dict = dict(p_models.PartStorageCollection.objects.filter(
                        part=self.data.get('%s-part' % self.prefix)
                    ).values_list('storage_id', 'quantity'))
                    s_qs = p_models.Storage.objects.filter(id__in=s_dict.keys())
                    self.fields['from_storage'].queryset = s_qs
                    self.fields['from_storage'].choices = [(None, '----------')] + [(s.id, '%s (%s)' % (s.__str__(), s_dict[s.id])) for s in s_qs]

        else:
            self.initial['part'] = self.instance.part
            self.fields['part'].queryset = p_models.Part.objects.filter(pk=self.instance.part.id)
            if self.instance.from_storage:
                self.initial['from_storage'] = self.instance.from_storage
                s_dict = dict(p_models.PartStorageCollection.objects.filter(
                    part=self.instance.part, storage__isnull=False, quantity__gt=0
                ).values_list('storage_id', 'quantity'))
                if self.instance.from_storage.id not in s_dict:
                    s_dict[self.instance.from_storage.id] = 0
            else:
                s_dict = dict(p_models.PartStorageCollection.objects.filter(
                    part=self.instance.part, storage__isnull=False, quantity__gt=0
                ).values_list('storage_id', 'quantity'))

            s_qs = p_models.Storage.objects.filter(id__in=s_dict.keys())
            self.fields['from_storage'].queryset = s_qs
            # Edit choices to insert quantity of part in storage
            self.fields['from_storage'].choices = [(None, '----------')] + [(s.id, '%s (%s)' % (s.__str__(), s_dict[s.id])) for s in s_qs]

        self.fields['part'].widget.attrs['data-prefix'] = self.prefix

        for f in self.fields:
            self.fields[f].widget.attrs['class'] = 'form-control'

        self.fields['quantity'].widget.attrs['class'] += ' parts-used-quantity max-width-50'
        self.fields['part'].widget.attrs['class'] += ' parts-used-part'
        self.fields['from_storage'].widget.attrs['class'] += ' parts-used-from_storage'


PartUsedFormset = forms.inlineformset_factory(sl_models.ServiceEvent, p_models.PartUsed, form=PartUsedForm, extra=2)


class CostInputField(forms.CharField):

    widget = forms.TextInput()

    def to_python(self, value):
        value = value.replace('$', '').replace(',', '')
        if value == '':
            raise ValidationError(self.error_messages['required'], code='required')
        if float(value) < 0:
            raise ValidationError('Ensure this value is greater than or equal to 0.')
        return value


class PartForm(BetterModelForm):

    cost = CostInputField()

    class Meta:
        model = p_models.Part
        fieldsets = [
            ('hidden_fields', {
                'fields': [],
            }),
            ('required_fields', {
                'fields': [
                    'part_number', 'cost', 'quantity_min'
                ],
            }),
            ('optional_fields', {
                'fields': [
                    'alt_part_number', 'part_category', 'is_obsolete'
                ]
            }),
            ('description_and_notes', {
                'fields': [
                    'description', 'notes'
                ]
            })
        ]

    def __init__(self, *args, **kwargs):
        super(PartForm, self).__init__(*args, **kwargs)

        self.fields['quantity_min'].widget.attrs.update({'min': 0, 'step': 1})

        for f in ['part_number', 'cost', 'quantity_min', 'alt_part_number', 'part_category']:
            self.fields[f].widget.attrs['class'] = 'form-control'

        for f in ['description', 'notes']:
            self.fields[f].widget.attrs['class'] = 'form-control autosize'
            self.fields[f].widget.attrs['rows'] = 3
            self.fields[f].widget.attrs['cols'] = 4

        for f in ['part_number', 'cost', 'quantity_min', 'description']:
            self.fields[f].widget.attrs['placeholder'] = 'required'


class PartSupplierCollectionForm(forms.ModelForm):

    class Meta:
        fields = ('part', 'supplier', 'part_number')
        model = p_models.PartSupplierCollection

    def __init__(self, *args, **kwargs):
        super(PartSupplierCollectionForm, self).__init__(*args, **kwargs)
        self.fields['part'].widget = forms.HiddenInput()

        self.fields['part_number'].widget.attrs['class'] = 'form-control part_number'
        self.fields['supplier'].widget.attrs['class'] = 'form-control supplier'


PartSupplierCollectionFormset = forms.inlineformset_factory(
    p_models.Part, p_models.PartSupplierCollection, form=PartSupplierCollectionForm, extra=3
)


class LocationField(forms.ChoiceField):

    # Validation really done by hidden storage field
    def validate(self, value):
        return value

    def has_changed(self, initial, data, tliib=False):
        return False


class StorageField(forms.ChoiceField):

    def clean(self, value):
        """

        Args:
            value: Either the pk of the storage as selected by room and location, or a string in the format
            of '__new__<name>'.

        Returns:
            String: if new storage is to be created. Returned value is location of new storage.
            None: if field was empty. Form will raise Validation error on room field instead since this field is hidden.
            Storage: if value was given as existing storage id.
            (field_name, ValidationError):  To raise ValidationError on releated field in form.
        """
        if value in [None, '']:
            return None
        elif '__new__' in value:
            value = value.replace('__new__', '')
            if value.strip() == '':
                return 'location', ValidationError('Invalid location')
        else:
            try:
                storage = p_models.Storage.objects.get(pk=value)
                return storage
            except ObjectDoesNotExist:
                return 'room', ValidationError("Incorrect Storage value")

    def has_changed(self, initial, data, tliib=False):
        if initial is None:
            if data in [None, '']:
                return False
            return True
        else:
            return force_text(initial) != force_text(data)


class PartStorageCollectionForm(forms.ModelForm):

    room = forms.ModelChoiceField(
        required=False, help_text=p_models.Storage._meta.get_field('room').help_text,
        queryset=p_models.Room.objects.all()
    )
    location = LocationField(required=False)
    storage_field = StorageField(widget=forms.TextInput())

    class Meta:
        model = p_models.PartStorageCollection

        fields = ('storage_field', 'room', 'location', 'quantity')

    def __init__(self, *args, **kwargs):
        super(PartStorageCollectionForm, self).__init__(*args, **kwargs)

        is_new = self.instance.id is None

        if not is_new:
            self.initial['room'] = self.instance.storage.room
            self.initial['storage_field'] = self.instance.storage.id
            self.initial['location'] = self.instance.storage.id
            self.fields['location'].widget.choices = [(self.instance.storage.id, '')]

        self.fields['room'].widget.attrs['class'] = 'form-control room'
        self.fields['quantity'].widget.attrs['class'] = 'form-control quantity'
        self.fields['location'].widget.attrs['class'] = 'form-control location'
        self.fields['storage_field'].widget.attrs['class'] = 'storage_field'
        self.fields['location'].widget.attrs.update({'disabled': True})

        location_data = self.data.get('%s-location' % self.prefix, [])
        if '__new__' in location_data:
            self.fields['location'].widget.choices.append(
                (location_data, location_data.replace('__new__', ''))
             )
            self.initial['location'] = location_data

    def clean(self):
        cleaned_data = super(PartStorageCollectionForm, self).clean()
        storage_field_value = cleaned_data.get('storage_field')
        room = cleaned_data.get('room')

        if storage_field_value is None:
            self.add_error('room', 'This field is required')
        elif isinstance(storage_field_value, str):
            if p_models.Storage.objects.filter(location=storage_field_value, room=room).exists():
                self.add_error(None, 'New room/location combination already exists.')
        elif isinstance(storage_field_value, p_models.Storage):
            if storage_field_value.room_id != room.id:
                self.add_error(None, 'Incorrect room/storage combination.')
        elif isinstance(storage_field_value, tuple):
            self.add_error(storage_field_value[0], storage_field_value[1])

        return cleaned_data


PartStorageCollectionFormset = forms.inlineformset_factory(
    p_models.Part, p_models.PartStorageCollection, form=PartStorageCollectionForm, extra=3
)
