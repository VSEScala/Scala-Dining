from django.urls import include, path

from dining import views

urlpatterns = [
    path("", views.index, name="index"),
    path("csv/", views.DailyDinersCSVView.as_view(), name="diners_csv"),
    path(
        "<int:year>/<int:month>/<int:day>/",
        include(
            [
                path("", views.DayView.as_view(), name="day_view"),
                path("add/", views.NewSlotView.as_view(), name="new_slot"),
                path(
                    "<slug:identifier>/",
                    include(
                        [
                            path("", views.SlotInfoView.as_view(), name="slot_details"),
                            path(
                                "list/", views.SlotListView.as_view(), name="slot_list"
                            ),
                            path(
                                "allergy/",
                                views.SlotAllergyView.as_view(),
                                name="slot_allergy",
                            ),
                            path(
                                "entry/add/",
                                views.EntryAddView.as_view(),
                                name="entry_add",
                            ),
                            path(
                                "change/",
                                views.SlotInfoChangeView.as_view(),
                                name="slot_change",
                            ),
                            path(
                                "delete/",
                                views.SlotDeleteView.as_view(),
                                name="slot_delete",
                            ),
                            path(
                                "inform_payment/",
                                views.SlotPaymentView.as_view(),
                                name="slot_inform_payment",
                            ),
                        ]
                    ),
                ),
            ]
        ),
    ),
    path(
        "entries/<int:pk>/delete/", views.EntryDeleteView.as_view(), name="entry_delete"
    ),
    path("statistics/", views.StatisticsView.as_view(), name="statistics"),
]
