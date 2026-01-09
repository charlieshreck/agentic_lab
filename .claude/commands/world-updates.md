# World Updates (Security & Best Practices)

Check for relevant security updates and best practices:

1. Get current deployed versions from the cluster
   ```bash
   kubectl get deployments -A -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}: {.spec.template.spec.containers[0].image}{"\n"}{end}'
   ```

2. Search for CVEs affecting:
   - Kubernetes version
   - Talos Linux version
   - Key applications (ArgoCD, cert-manager, etc.)

3. Check for deprecated features in use

4. Review best practice updates for:
   - Kubernetes security
   - GitOps workflows
   - Container security

Format output as:

```
=== WORLD UPDATES ===

🔒 Security Advisories:
  - [HIGH] CVE-2024-XXXX: Description (affects: component)
  - [MED] CVE-2024-YYYY: Description (affects: component)

⚠️ Deprecations:
  - Feature X deprecated in K8s 1.30 (we use: yes/no)

📖 Best Practices:
  - New: Description of best practice update

🔄 Available Updates:
  - ArgoCD: 2.10.0 → 2.11.0
  - cert-manager: 1.14.0 → 1.15.0

Actions Required: X items need attention
```

Note: This command performs web searches to check for updates. Results should be reviewed before taking action.
