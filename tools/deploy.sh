#!/bin/bash

set -euxo pipefail

cd `dirname $0`

JOBNAME=$(kubectl create -f deploy.yaml -o name)
kubectl wait --for=condition=complete $JOBNAME
kubectl delete $JOBNAME
kubectl apply -f vpncheck-deployment.yaml
kubectl delete pods --all
