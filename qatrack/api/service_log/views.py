from rest_framework import viewsets
from rest_framework.filters import OrderingFilter
from rest_framework_filters import backends

from qatrack.api.service_log import filters, serializers
from qatrack.service_log import models


class ServiceAreaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.ServiceArea.objects.all()
    serializer_class = serializers.ServiceAreaSerializer
    filter_class = filters.ServiceAreaFilter
    filter_backends = (backends.DjangoFilterBackend, OrderingFilter,)


class UnitServiceAreaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.UnitServiceArea.objects.all()
    serializer_class = serializers.UnitServiceAreaSerializer
    filter_class = filters.UnitServiceAreaFilter
    filter_backends = (backends.DjangoFilterBackend, OrderingFilter,)


class ServiceTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.ServiceType.objects.all()
    serializer_class = serializers.ServiceTypeSerializer
    filter_class = filters.ServiceTypeFilter
    filter_backends = (backends.DjangoFilterBackend, OrderingFilter,)


class ServiceEventStatusViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.ServiceEventStatus.objects.all()
    serializer_class = serializers.ServiceEventStatusSerializer
    filter_class = filters.ServiceEventStatusFilter
    filter_backends = (backends.DjangoFilterBackend, OrderingFilter,)


class ServiceEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.ServiceEvent.objects.all()
    serializer_class = serializers.ServiceEventSerializer
    filter_class = filters.ServiceEventFilter
    filter_backends = (backends.DjangoFilterBackend, OrderingFilter,)


class ThirdPartyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.ThirdParty.objects.all()
    serializer_class = serializers.ThirdPartySerializer
    filter_class = filters.ThirdPartyFilter
    filter_backends = (backends.DjangoFilterBackend, OrderingFilter,)


class HoursViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Hours.objects.all()
    serializer_class = serializers.HoursSerializer
    filter_class = filters.HoursFilter
    filter_backends = (backends.DjangoFilterBackend, OrderingFilter,)


class ReturnToServiceQAViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.ReturnToServiceQA.objects.all()
    serializer_class = serializers.ReturnToServiceQASerializer
    filter_class = filters.ReturnToServiceQAFilter
    filter_backends = (backends.DjangoFilterBackend, OrderingFilter,)


class GroupLinkerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.GroupLinker.objects.all()
    serializer_class = serializers.GroupLinkerSerializer
    filter_class = filters.GroupLinkerFilter
    filter_backends = (backends.DjangoFilterBackend, OrderingFilter,)


class GroupLinkerInstanceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.GroupLinkerInstance.objects.all()
    serializer_class = serializers.GroupLinkerInstanceSerializer
    filter_class = filters.GroupLinkerInstanceFilter
    filter_backends = (backends.DjangoFilterBackend, OrderingFilter,)
