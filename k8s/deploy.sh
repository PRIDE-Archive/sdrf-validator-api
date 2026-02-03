#!/bin/bash
# Deploy SDRF Validator API to Kubernetes
# Apply once (namespace, configmap, deployment, service, ingress).
# When CI pushes a new image to GHCR, run: kubectl rollout restart deployment/sdrf-validator -n sdrf-validator

set -e

NAMESPACE="sdrf-validator"

echo "Deploying SDRF Validator API..."

# Create namespace
echo "Creating namespace..."
kubectl apply -f namespace.yaml

# Apply ConfigMap
echo "Applying ConfigMap..."
kubectl apply -f configmap.yaml

# Deploy the application
echo "Deploying application..."
kubectl apply -f deployment.yaml

# Create service
echo "Creating service..."
kubectl apply -f service.yaml

# Apply Ingress (PRIDE services host/path)
echo "Applying Ingress (ingress-pride-services.yaml)..."
kubectl apply -f ingress-pride-services.yaml

echo ""
echo "Deployment complete!"
echo ""
echo "When a new image is pushed by CI, rollout to pick it up:"
echo "  kubectl rollout restart deployment/sdrf-validator -n ${NAMESPACE}"
echo ""
echo "To check status:"
echo "  kubectl get pods -n ${NAMESPACE}"
echo ""
echo "To port-forward locally:"
echo "  kubectl port-forward -n ${NAMESPACE} svc/sdrf-validator-service 8080:80"
echo "  Then open: http://localhost:8080/docs"
