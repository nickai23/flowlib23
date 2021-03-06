# NiFi Kubernetes deployment options #

### Local ###

```bash
# Bootstrap cluster
$ kubectl apply -k ./k8s/app/bootstrap
```

Run: `kubectl port-forward svc/nifi 8080:8080`
The NiFi UI is available at: `http://localhost:8080/nifi/`

To use NiFi and FlowLib through BDP, add the local cluster through the BDP UI:
```bash
# Get Cluster Endpoint.
# Note that if the endpoint is localhost you'll need to change it to 127.0.0.1, otherwise cert verification fails
$ kubectl config view --minify --raw -o jsonpath='{.clusters[0].cluster.server}'

# Get Service Account Token data and CA Cert data
$ kubectl -o json -n b23-data-platform get secrets | jq '.items[] | select(.metadata.name | startswith("b23-")) | {token: .data.token | @base64d, ca_cert: .data."ca.crt" }'
```

Run this on your cluster to create the ImagePullSecret for pulling images from ECR

```bash
#!/usr/bin/env bash
login_cmd=$(aws ecr get-login)
username=$(echo $login_cmd | cut -d " " -f 4)
password=$(echo $login_cmd | cut -d " " -f 6)
endpoint=$(echo $login_cmd | cut -d " " -f 9)
auth=$(echo "$username:$password" | /usr/bin/base64)

configjson="{ \"auths\": { \"${endpoint}\": { \"auth\": \"${auth}\" } } }"

kubectl create -f - << EOF
apiVersion: v1
kind: Secret
metadata:
  name: aws-ecr-registry
data:
  .dockerconfigjson: $(echo $configjson | /usr/bin/base64)
type: kubernetes.io/dockerconfigjson
EOF
```

ECR registry policy json

```json
{
  "Version": "2008-10-17",
  "Statement": [
    {
      "Sid": "AllowPullForB23UserAccounts",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::883886641571:root"
      },
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer"
      ]
    }
  ]
}
```
