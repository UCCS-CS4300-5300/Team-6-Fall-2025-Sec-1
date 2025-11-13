from django.contrib import admin
from .models import Itinerary, BreakTime, BudgetItem, Day


class BreakTimeInline(admin.TabularInline):
    model = BreakTime
    extra = 0


class BudgetItemInline(admin.TabularInline):
    model = BudgetItem
    extra = 0


class DayInline(admin.TabularInline):
    model = Day
    extra = 0


@admin.register(Itinerary)
class ItineraryAdmin(admin.ModelAdmin):
    list_display = ['destination', 'num_days', 'wake_up_time', 'bed_time', 'created_at']
    list_filter = ['created_at', 'num_days']
    search_fields = ['destination', 'place_id']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [BreakTimeInline, BudgetItemInline, DayInline]
    fieldsets = (
        ('Destination', {
            'fields': ('destination', 'place_id', 'latitude', 'longitude')
        }),
        ('Time Preferences', {
            'fields': ('wake_up_time', 'bed_time')
        }),
        ('Trip Details', {
            'fields': ('num_days',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(BreakTime)
class BreakTimeAdmin(admin.ModelAdmin):
    list_display = ['itinerary', 'start_time', 'end_time']
    list_filter = ['itinerary']


@admin.register(BudgetItem)
class BudgetItemAdmin(admin.ModelAdmin):
    list_display = ['itinerary', 'category', 'custom_category', 'amount']
    list_filter = ['category', 'itinerary']
    search_fields = ['category', 'custom_category']


@admin.register(Day)
class DayAdmin(admin.ModelAdmin):
    list_display = ['itinerary', 'day_number', 'date', 'notes']
    list_filter = ['itinerary', 'date']
    search_fields = ['notes']
