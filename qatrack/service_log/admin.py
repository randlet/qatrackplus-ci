from django.conf import settings
from django.contrib import admin
from django.forms import ModelForm, ValidationError

from .models import (
    GroupLinker,
    ServiceArea,
    ServiceEvent,
    ServiceEventStatus,
    ServiceType,
    ThirdParty,
    UnitServiceArea,
)


class ServiceEventStatusFormAdmin(ModelForm):

    class Meta:
        model = ServiceEventStatus
        fields = '__all__'

    def clean_is_default(self):

        is_default = self.cleaned_data['is_default']
        if not is_default and self.initial.get('is_default', False):
            raise ValidationError('There must be one default status. Edit another status to be default first.')
        return is_default


class DeleteOnlyFromOwnFormAdmin(admin.ModelAdmin):

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return False
        return super(DeleteOnlyFromOwnFormAdmin, self).has_delete_permission(request, obj)


class ServiceEventAdmin(DeleteOnlyFromOwnFormAdmin):

    list_display = [
        "get_se_id",
        "unit_service_area",
        "service_type",
        "service_status",
        "datetime_created",
        "datetime_modified",
        "is_review_required",
        "is_active",
    ]

    list_filter = ["unit_service_area", "service_type", "is_review_required", "is_active"]

    raw_id_fields = [
        "test_list_instance_initiated_by",
    ]

    filter_horizontal = ["service_event_related"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):

        if db_field.name == "unit_service_area":
            kwargs['queryset'] = UnitServiceArea.objects.select_related("unit", "service_area")

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_se_id(self, obj):
        return "Service Event #%d" % obj.pk

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.select_related(
            "unit_service_area",
            "unit_service_area__service_area",
            "unit_service_area__unit",
        )
        return qs


class ServiceEventStatusAdmin(DeleteOnlyFromOwnFormAdmin):
    list_display = ['name', 'is_review_required', 'is_default', 'rts_qa_must_be_reviewed']
    form = ServiceEventStatusFormAdmin

    class Media:
        js = (
            settings.STATIC_URL + "jquery/js/jquery.min.js",
            settings.STATIC_URL + "colorpicker/js/bootstrap-colorpicker.min.js",
            settings.STATIC_URL + "qatrack_core/js/admin_colourpicker.js",

        )
        css = {
            'all': (
                settings.STATIC_URL + "bootstrap/css/bootstrap.min.css",
                settings.STATIC_URL + "colorpicker/css/bootstrap-colorpicker.min.css",
                settings.STATIC_URL + "qatrack_core/css/admin.css",
            ),
        }

    def delete_view(self, request, object_id, extra_context=None):

        if ServiceEventStatus.objects.get(pk=object_id).is_default:
            extra_context = extra_context or {'is_default': True}

        return super().delete_view(request, object_id, extra_context)


class ServiceTypeAdmin(DeleteOnlyFromOwnFormAdmin):
    list_display = ['name', 'is_review_required', 'is_active']


class ServiceAreaAdmin(DeleteOnlyFromOwnFormAdmin):
    list_display = ['name']
    filter_horizontal = ("units",)


class UnitServiceAreaAdmin(DeleteOnlyFromOwnFormAdmin):
    list_display = ['__str__', 'notes']
    list_filter = ['unit', 'service_area']
    search_fields = ['unit__name', 'service_area__name']


class GroupLinkerAdmin(DeleteOnlyFromOwnFormAdmin):
    list_display = ['name', 'group', 'description', 'help_text']
    list_filter = ['group']
    search_fields = ['name', 'group__name']


if settings.USE_SERVICE_LOG:
    admin.site.register(ServiceArea, ServiceAreaAdmin)
    admin.site.register(ServiceEvent, ServiceEventAdmin)
    admin.site.register(ServiceType, ServiceTypeAdmin)
    admin.site.register(ServiceEventStatus, ServiceEventStatusAdmin)
    admin.site.register(UnitServiceArea, UnitServiceAreaAdmin)
    admin.site.register(GroupLinker, GroupLinkerAdmin)

    admin.site.register([ThirdParty], admin.ModelAdmin)
