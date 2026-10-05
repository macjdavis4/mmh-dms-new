from django.contrib import admin

from .models import Quote, QuoteLine, Sale, SaleUnitChange, TradeIn


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["number", "customer", "status", "quote_date"]
    list_filter = ["status"]
    search_fields = ["number", "customer__name"]


for model in (QuoteLine, TradeIn, Sale, SaleUnitChange):
    admin.site.register(model)
