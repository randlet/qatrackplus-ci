
from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import ugettext as _

from qatrack.units import models as u_models
from qatrack.service_log import models as sl_models


class Supplier(models.Model):

    name = models.CharField(max_length=32, unique=True)
    notes = models.TextField(
        max_length=255, blank=True, null=True, help_text=_('Additional comments about this supplier')
    )

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class RoomManager(models.Manager):

    def get_queryset(self):
        return super(RoomManager, self).get_queryset().select_related('site')


class Room(models.Model):

    site = models.ForeignKey(u_models.Site, blank=True, null=True, help_text=_('Site this storage room is located'))
    name = models.CharField(max_length=32, help_text=_('Name of room or room number'))

    objects = RoomManager()

    class Meta:
        ordering = ['site', 'name']
        unique_together = ['site', 'name']

    def __str__(self):
        return '%s%s' % (self.name, ' (%s)' % self.site.name if self.site else '')

    def save(self, *args, **kwargs):
        new = self.pk is None
        super().save(*args, **kwargs)
        if new:
            # Create generic storage (ie, no location)
            Storage.objects.create(room=self)


class StorageManager(models.Manager):

    def get_queryset(self):
        return super(StorageManager, self).get_queryset().select_related('room', 'room__site').order_by('location')

    def get_queryset_for_room(self, room):
        return super().get_queryset().filter(room=room).order_by('location')


class Storage(models.Model):

    room = models.ForeignKey(Room, blank=True, null=True, help_text=_('Room for part storage'), on_delete=models.CASCADE)

    location = models.CharField(max_length=32, blank=True, null=True)
    description = models.TextField(max_length=255, null=True, blank=True)

    objects = StorageManager()

    class Meta:
        verbose_name_plural = 'Storage'
        unique_together = ['room', 'location']

    def __str__(self):
        items = []
        if self.room:
            if self.room.site:
                items.append(self.room.site.name)
            items.append(self.room.name)
        if self.location:
            items.append(self.location)
        else:
            items.append('<no location>')

        return ' - '.join(items)


class PartCategory(models.Model):

    name = models.CharField(max_length=64)

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name


class Part(models.Model):

    name = models.CharField(help_text=_('Brief name describing this part'), max_length=255)
    part_category = models.ForeignKey(PartCategory, blank=True, null=True)
    suppliers = models.ManyToManyField(
        Supplier, blank=True, help_text=_('Suppliers of this part'), related_name='parts',
        through='PartSupplierCollection'
    )
    storage = models.ManyToManyField(
        Storage, through='PartStorageCollection', related_name='parts', help_text=_('Storage locations for this part')
    )

    part_number = models.CharField(max_length=32, unique=True)
    alt_part_number = models.CharField(
        max_length=32, blank=True, null=True, verbose_name=_('Alternate part number')
    )
    quantity_min = models.PositiveIntegerField(
        default=0, help_text=_('Notify when the quantity of this part in storage falls below this number'),
    )
    quantity_current = models.PositiveIntegerField(help_text=_('The number of parts in storage currently'), default=0, editable=False)
    cost = models.DecimalField(
        default=0, decimal_places=2, max_digits=10, help_text=_('Cost of this part'), null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    notes = models.TextField(max_length=255, blank=True, null=True, help_text=_('Additional comments about this part'))
    is_obsolete = models.BooleanField(default=False, help_text=_('Is this part now obsolete?'))

    class Meta:
        permissions = (('view_part', 'Can View Part'),)
        ordering = ['part_number']

    def __str__(self):
        return '%s%s - %s' % (self.part_number, ' (%s)' % self.alt_part_number if self.alt_part_number else '', self.name)

    def set_quantity_current(self):
        qs = PartStorageCollection.objects.filter(part=self, storage__isnull=False)
        if qs.exists():
            self.quantity_current = qs.aggregate(models.Sum('quantity'))['quantity__sum']
        else:
            self.quantity_current = 0
        self.quantity_current = self.quantity_current if self.quantity_current >= 0 else 0
        self.save()
        return self.quantity_current < self.quantity_min


class PartStorageCollectionManager(models.Manager):

    def get_queryset(self):
        return super(PartStorageCollectionManager, self).get_queryset().select_related(
            'storage', 'part', 'storage__room', 'storage__room__site'
        ).order_by(
            '-quantity',
            'part__part_number'
        )


class PartStorageCollection(models.Model):

    part = models.ForeignKey(Part)
    storage = models.ForeignKey(Storage)

    quantity = models.IntegerField()

    objects = PartStorageCollectionManager()

    class Meta:
        unique_together = ('part', 'storage')
        default_permissions = ()

    def save(self, *args, **kwargs):
        self.quantity = self.quantity if self.quantity >= 0 else 0
        super(PartStorageCollection, self).save(*args, **kwargs)
        self.part.set_quantity_current()

    def __str__(self):
        locs = []
        if self.storage.room.site:
            locs.append(self.storage.room.site.name)
        locs.append(self.storage.room.name)
        if self.storage.location:
            locs.append(self.storage.location)
        locs.append('(%s)' % self.quantity)
        return ' - '.join(locs)


class PartSupplierCollection(models.Model):

    part = models.ForeignKey(Part, on_delete=models.CASCADE)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    part_number = models.CharField(
        max_length=32, null=True, blank=True,
        help_text=_('Does this supplier have a different part number for this part')
    )

    class Meta:
        unique_together = ('part', 'supplier')
        default_permissions = ()


class PartUsed(models.Model):

    service_event = models.ForeignKey(sl_models.ServiceEvent, on_delete=models.CASCADE)
    part = models.ForeignKey(Part, help_text=_('Select the part used'), on_delete=models.CASCADE)
    from_storage = models.ForeignKey(Storage, null=True, blank=True, on_delete=models.SET_NULL)

    quantity = models.IntegerField()

    def add_back_to_storage(self):

        if self.from_storage:
            try:
                psc = PartStorageCollection.objects.get(part=self.part, storage=self.from_storage)
                psc.quantity += self.quantity
                psc.save()
            except PartStorageCollection.DoesNotExist:
                PartStorageCollection.objects.create(part=self.part, storage=self.from_storage, quantity=self.quantity)

    def remove_from_storage(self):

        if self.from_storage:
            try:
                psc = PartStorageCollection.objects.get(part=self.part, storage=self.from_storage)
                psc.quantity -= self.quantity
                psc.save()
            except PartStorageCollection.DoesNotExist:
                pass
