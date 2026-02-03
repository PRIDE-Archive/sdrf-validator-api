#!/bin/bash
# Deploy SDRF Validator API to Kubernetes

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

# Apply HPA
echo "Applying HorizontalPodAutoscaler..."
kubectl apply -f hpa.yaml

# Apply Ingress (optional - comment out if not using ingress)
# echo "Applying Ingress..."
# kubectl apply -f ingress.yaml

echo ""
echo "Deployment complete!"
echo ""
echo "To check the status:"
echo "  kubectl get pods -n ${NAMESPACE}"
echo ""
echo "To access locally (port-forward):"
echo "  kubectl port-forward -n ${NAMESPACE} svc/sdrf-validator-service 8080:80"
echo "  Then open: http://localhost:8080/docs"
