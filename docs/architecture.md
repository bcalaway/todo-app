# Architecture

This page shows how a change to todo-app travels from a spoken or typed request to a live deploy, and which pieces of infrastructure it runs on. The app follows the home platform's app contract; for what each integration point means, see [docs/app-platform.md](https://github.com/bcalaway/nyc_pa_aws_gitops/blob/main/docs/app-platform.md) in the platform repo `nyc_pa_aws_gitops`.

## DevOps workflow

```mermaid
flowchart TD
    A["Bill asks by voice or chat"] --> B["Claude calls Home platform<br/>start_task tool"]
    B --> C["Coding agent on nuc4 (NYC)<br/>changes todo-app, runs tests,<br/>opens a PR"]
    C --> D["PR check: app-ci.yml<br/>(reusable, from nyc_pa_aws_gitops)<br/>docker build --target lint<br/>--target test, then plain build"]
    D --> E{"Bill reviews<br/>and merges to main"}
    E --> F["app-build-push.yml<br/>build final stage, tag git SHA + latest,<br/>push to ECR via GitHub OIDC"]
    F --> G["app-deploy.yml (auto-deploy)<br/>stage deploy/docker-compose.yml<br/>to S3 apps/todo-app/"]
    G --> H["ssm:SendCommand<br/>triggers the hub"]
    H --> I["Hub script: pull Compose file and image,<br/>build .env from SSM<br/>/home-platform/todo-app/*,<br/>docker compose pull && up -d"]
    I --> J["Live at subdomain<br/>/health returns 200"]
```

- The coding agent never merges or deploys; the merge by Bill is the only human approval gate.
- `app-ci.yml` is called via `workflow_call` and is a required check on PRs.
- Images are pushed with GitHub OIDC using the app's own least-privilege IAM role, so there are no long-lived keys.
- GitHub runners cannot reach the hub directly (its security group only allows WireGuard subnets), so the deploy goes through S3 (`home-platform-ansible-deploy-<account>`) and `ssm:SendCommand`.
- Production only, with no staging tier (ADR-0019).

## Infrastructure

```mermaid
flowchart LR
    User["Browser"] --> DNS["Route 53<br/>app.billandjessie.com"]
    DNS --> EIP["Hub Elastic IP"]

    subgraph GH["GitHub"]
        Repo["todo-app repo"]
        Plat["nyc_pa_aws_gitops<br/>reusable workflows"]
        GHA["GitHub Actions"]
        Repo --> GHA
        Plat -. workflow_call .-> GHA
    end

    subgraph AWS["AWS"]
        ECR["ECR: todo-app"]
        IAM["IAM OIDC role<br/>for todo-app"]
        S3["S3 deploy bucket"]
        SSM["SSM: Parameter Store<br/>+ SendCommand"]
        TF["Terraform state (S3)"]

        subgraph HUB["Hub EC2 (10.0.3.1)"]
            Traefik["Traefik<br/>TLS via Route 53, HSTS,<br/>optional Authentik forward-auth"]
            App["todo-app container"]
            PG[("Shared Postgres<br/>todo-app DB + role")]
            Redis[("Redis")]
            Auth["Authentik"]
            Obs["Observability<br/>Grafana etc."]
        end
    end

    subgraph NYC["NYC site"]
        NYCR["Router"]
        NUC4["nuc4<br/>build server + coding agent"]
        NUC4 --- NYCR
    end

    subgraph RAM["Rambles site"]
        RAMR["Router"]
        NUC5["nuc5"]
        NUC5 --- RAMR
    end

    GHA -- OIDC --> IAM
    GHA --> ECR
    GHA --> S3
    GHA -- SendCommand --> SSM
    NUC4 -. opens PRs .-> Repo

    EIP --> Traefik --> App
    App --> PG
    Traefik -.-> Auth
    App -. pulls image .-> ECR
    HUB -. reads config .-> SSM
    HUB -. reads Compose .-> S3

    NYCR == WireGuard ==> HUB
    RAMR == WireGuard ==> HUB
```

- All hub services share the `home-platform` Docker network.
- todo-app has its own logical Postgres database and a least-privilege role on the shared instance.
- Both home sites reach the hub over WireGuard, which is also the only network the hub's security group allows in for management.
- Terraform state lives in S3.
