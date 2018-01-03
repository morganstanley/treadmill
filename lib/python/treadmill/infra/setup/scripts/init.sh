#!/bin/bash -e

# This script makes sure instance is ready to be configured.

TIMEOUT=120

retry_count=0
until ( ping -c 1 aws.amazon.com ) || [ $retry_count -eq $TIMEOUT ]
do
    retry_count=`expr $retry_count + 1`
    sleep 1
done
