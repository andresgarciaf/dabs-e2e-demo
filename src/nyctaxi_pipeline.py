"""Trivial SDP pipeline: read the nyctaxi samples table, land two tables.

Kept deliberately small - the point of this repo is the dev -> PR -> prod
promotion flow, not the data engineering.
"""
import dlt
from pyspark.sql import functions as F

# Set per target in the pipeline `configuration` block (see nyctaxi.pipeline.yml).
SOURCE = spark.conf.get("source_table")


@dlt.table(comment="Raw NYC taxi trips copied from the samples catalog.")
def trips_bronze():
    return spark.read.table(SOURCE)


@dlt.table(comment="Trip counts and average fare/distance per pickup day.")
def daily_fares():
    return (
        dlt.read("trips_bronze")
        .groupBy(F.to_date("tpep_pickup_datetime").alias("pickup_date"))
        .agg(
            F.count("*").alias("trip_count"),
            F.round(F.avg("fare_amount"), 2).alias("avg_fare"),
            F.round(F.avg("trip_distance"), 2).alias("avg_distance"),
        )
    )
