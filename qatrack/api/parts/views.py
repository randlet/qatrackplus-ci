from rest_framework import viewsets
from rest_framework.filters import OrderingFilter
from rest_framework_filters import backends

from qatrack.api.parts import filters, serializers
from qatrack.parts import models


class SupplierViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Supplier.objects.all()
    serializer_class = serializers.SupplierSerializer
    filter_class = filters.SupplierFilter
    filter_backends = (backends.DjangoFilterBackend, OrderingFilter,)


class StorageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Storage.objects.all()
    serializer_class = serializers.StorageSerializer
    filter_class = filters.StorageFilter
    filter_backends = (backends.DjangoFilterBackend, OrderingFilter,)


class PartCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.PartCategory.objects.all()
    serializer_class = serializers.PartCategorySerializer
    filter_class = filters.PartCategoryFilter
    filter_backends = (backends.DjangoFilterBackend, OrderingFilter,)


class PartViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Part.objects.all()
    serializer_class = serializers.PartSerializer
    filter_class = filters.PartFilter
    filter_backends = (backends.DjangoFilterBackend, OrderingFilter,)


class PartStorageCollectionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.PartStorageCollection.objects.all()
    serializer_class = serializers.PartStorageCollectionSerializer
    filter_class = filters.PartStorageCollectionFilter
    filter_backends = (backends.DjangoFilterBackend, OrderingFilter,)


class PartSupplierCollectionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.PartSupplierCollection.objects.all()
    serializer_class = serializers.PartSupplierCollectionSerializer
    filter_class = filters.PartSupplierCollectionFilter
    filter_backends = (backends.DjangoFilterBackend, OrderingFilter,)


class PartUsedViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.PartUsed.objects.all()
    serializer_class = serializers.PartUsedSerializer
    filter_class = filters.PartUsedFilter
    filter_backends = (backends.DjangoFilterBackend, OrderingFilter,)
