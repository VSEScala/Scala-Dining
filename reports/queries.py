from django.conf import settings
from django.db.models import Count, F, OuterRef, Q, QuerySet, Subquery, Sum

from dining.models import DiningEntry
from userdetails.models import User, UserMembership

# These queries don't have test cases because they are for reporting and not critical.
# I have tested them manually and verified the generated SQL queries. The SQL queries
# are at the bottom.


def diner_counts(dining_lists: QuerySet, verified_only=True) -> QuerySet:
    """Groups by association and annotates the dining lists with entry counts.

    A diner is only counted as member of the association when the membership is
    verified.

    Returns:
        A dictionary queryset with the keys `association`, `total_diners`,
        `association_diners`, `outside_diners` and `guests`.
    """
    # The distinct is necessary because the generated join returns a separate row
    # for each (dining entry, membership) combination. If someone has two
    # memberships, they will have two rows with the same dining entry.
    association_count = Count(
        "dining_entries",
        filter=Q(
            dining_entries__external_name="",
            dining_entries__user__usermembership__association=F("association"),
            dining_entries__user__usermembership__is_verified=True,
        )
        if verified_only
        else Q(
            dining_entries__external_name="",
            dining_entries__user__usermembership__association=F("association"),
        ),
        distinct=True,
    )

    return dining_lists.values("association").annotate(
        total_diners=Count("dining_entries", distinct=True),
        association_diners=association_count,
        # Internal diner count minus association diner count
        outside_diners=Count(
            "dining_entries", filter=Q(dining_entries__external_name=""), distinct=True
        )
        - association_count,
        guests=Count(
            "dining_entries", filter=~Q(dining_entries__external_name=""), distinct=True
        ),
    )


# SQL for diners count
"""
SELECT
  "dining_dininglist"."association_id",
  COUNT(DISTINCT "dining_diningentry"."id") AS "total_diners",
  COUNT(DISTINCT "dining_diningentry"."id") FILTER (
    WHERE
      (
        "dining_diningentry"."external_name" =
        AND "userdetails_usermembership"."association_id" = ("dining_dininglist"."association_id")
        AND "userdetails_usermembership"."is_verified"
      )
  ) AS "association_diners",
  (
    COUNT(DISTINCT "dining_diningentry"."id") FILTER (
      WHERE
        "dining_diningentry"."external_name" =
    ) - COUNT(DISTINCT "dining_diningentry"."id") FILTER (
      WHERE
        (
          "dining_diningentry"."external_name" =
          AND "userdetails_usermembership"."association_id" = ("dining_dininglist"."association_id")
          AND "userdetails_usermembership"."is_verified"
        )
    )
  ) AS "outside_diners",
  COUNT(DISTINCT "dining_diningentry"."id") FILTER (
    WHERE
      NOT (
        "dining_diningentry"."external_name" =
        AND "dining_diningentry"."external_name" IS NOT NULL
      )
  ) AS "guests"
FROM
  "dining_dininglist"
  LEFT OUTER JOIN "dining_diningentry" ON (
    "dining_dininglist"."id" = "dining_diningentry"."dining_list_id"
  )
  LEFT OUTER JOIN "userdetails_user" ON (
    "dining_diningentry"."user_id" = "userdetails_user"."id"
  )
  LEFT OUTER JOIN "userdetails_usermembership" ON (
    "userdetails_user"."id" = "userdetails_usermembership"."related_user_id"
  )
WHERE
  (
    "dining_dininglist"."date" >= 2024 -01 -01
    AND "dining_dininglist"."date" < 2024 -02 -01
  )
GROUP BY
  "dining_dininglist"."association_id"
"""


def kitchen_usage(
    dining_lists: QuerySet, verified_only=True, include_guests=False
) -> QuerySet:
    """Computes weighted and non-weighted kitchen usage.

    Returns:
        A dictionary QuerySet with the keys `association_membership` (int),
        `weighted_usage` (float) and `not_weighted_usage` (int).
    """
    # Weight per user is 1.0 / (number of memberships)
    weight = Subquery(
        UserMembership.objects.filter(
            Q(related_user=OuterRef("user"), is_verified=True)
            if verified_only
            else Q(related_user=OuterRef("user"))
        )
        .values("related_user")
        .annotate(weight=1.0 / Count("association"))
        .values("weight")
    )

    q = Q(dining_list__in=dining_lists)
    if verified_only:
        q &= Q(user__usermembership__is_verified=True)
    if not include_guests:
        q &= Q(external_name="")  # Internal dining entries only

    qs = (
        DiningEntry.objects.filter(q)
        .annotate(
            membership_association=F("user__usermembership__association"), weight=weight
        )
        .values("membership_association")
        .annotate(
            not_weighted_usage=Count("id"),  # No need for distinct due to the grouping
            weighted_usage=Sum("weight"),
        )
    )
    if settings.DEBUG:
        print(qs.query)
    return qs


"""
SELECT
  "userdetails_usermembership"."association_id" AS "membership_association",
  COUNT("dining_diningentry"."id") AS "not_weighted",
  SUM(
    (
      SELECT
        (1.0 / COUNT(U0."association_id")) AS "weight"
      FROM
        "userdetails_usermembership" U0
      WHERE
        (
          U0."is_verified"
          AND U0."related_user_id" = ("dining_diningentry"."user_id")
        )
      GROUP BY
        U0."related_user_id"
    )
  ) AS "weighted"
FROM
  "dining_diningentry"
  INNER JOIN "userdetails_user" ON (
    "dining_diningentry"."user_id" = "userdetails_user"."id"
  )
  INNER JOIN "userdetails_usermembership" ON (
    "userdetails_user"."id" = "userdetails_usermembership"."related_user_id"
  )
WHERE
  (
    "dining_diningentry"."dining_list_id" IN (
      SELECT
        U0."id"
      FROM
        "dining_dininglist" U0
      WHERE
        (
          U0."date" >= 2024 -01 -01
          AND U0."date" < 2024 -02 -01
        )
    )
    AND "dining_diningentry"."external_name" =
    AND "userdetails_usermembership"."is_verified"
  )
GROUP BY
  1
"""


def dining_members_count(
    dining_lists: QuerySet, verified_only=True
) -> tuple[QuerySet, QuerySet]:
    """Computes distinct user counts per association who joined or owned a list.

    Returns:
        Two dictionary querysets, one with `joined` and one with `owned`.
    """

    def group_association(qs, key):
        return (
            qs.annotate(association=F("usermembership__association"))
            .values("association")
            .annotate(**{key: Count("id", distinct=True)})
        )

    # `Exists` might improve performance (and prevent the need for `distinct`).
    joined_q = Q(diningentry__dining_list__in=dining_lists)
    owned_q = Q(owned_dining_lists__in=dining_lists)
    if verified_only:
        joined_q &= Q(usermembership__is_verified=True)
        owned_q &= Q(usermembership__is_verified=True)
    return (
        group_association(User.objects.filter(joined_q), "joined"),
        group_association(User.objects.filter(owned_q), "owned"),
    )


"""
SELECT
  "userdetails_usermembership"."association_id" AS "association",
  COUNT("userdetails_user"."id") AS "individuals"
FROM
  "userdetails_user"
  INNER JOIN "dining_diningentry" ON (
    "userdetails_user"."id" = "dining_diningentry"."user_id"
  )
  INNER JOIN "userdetails_usermembership" ON (
    "userdetails_user"."id" = "userdetails_usermembership"."related_user_id"
  )
WHERE
  (
    "dining_diningentry"."dining_list_id" IN (
      SELECT
        U0."id"
      FROM
        "dining_dininglist" U0
      WHERE
        (
          U0."date" >= 2024 -01 -01
          AND U0."date" < 2024 -02 -01
        )
    )
    AND "userdetails_usermembership"."is_verified"
  )
GROUP BY
  1
"""


def count_help_stats(dining_lists: QuerySet) -> QuerySet:
    """Counts help stats per association."""
    return (
        DiningEntry.objects.filter(dining_list__in=dining_lists)
        .values("dining_list__association")
        .annotate(
            shop=Count("id", filter=Q(has_shopped=True)),
            cook=Count("id", filter=Q(has_cooked=True)),
            clean=Count("id", filter=Q(has_cleaned=True)),
        )
    )


def power_users(dining_lists: QuerySet) -> tuple[QuerySet, QuerySet]:
    """Returns two querysets of Users ordered by joined and owned lists."""
    qs = User.objects.annotate(
        joined_lists=Count(
            "diningentry",
            filter=Q(
                diningentry__external_name="", diningentry__dining_list__in=dining_lists
            ),
            distinct=True,
        ),
        owned_lists=Count(
            "owned_dining_lists",
            filter=Q(owned_dining_lists__in=dining_lists),
            distinct=True,
        ),
    )
    return qs.order_by("-joined_lists"), qs.order_by("-owned_lists")
