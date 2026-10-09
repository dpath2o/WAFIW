# Earthdata and ASF access: OS and Azure deployment prerequisites

**An approved outbound HTTPS path from the actual WAFIW worker to `urs.earthdata.nasa.gov` is a required deployment dependency.** Installing conda, Python and SNAP is not sufficient. The worker also needs a working Earthdata account, ASF application authorization, accepted applicable EULAs, and a valid credential available to the job process.

For Azure planning, include Earthdata access in the OS/runtime and network build specification, with a named owner and an acceptance test. A browser login from an administrator's laptop does not demonstrate access from a scheduled Azure job.

## Required deployment criterion

> Provision a controlled outbound connection from the WAFIW acquisition worker to NASA Earthdata Login (`urs.earthdata.nasa.gov`, HTTPS/TCP 443), including DNS resolution, valid TLS certificate verification and access to the authentication endpoints used by the installed ASF client. Provision access to the associated ASF catalogue and scene-download destinations as well. Before enabling scheduled acquisition, demonstrate successful token authentication and one authenticated Sentinel-1 download from the deployed worker identity and network path. Record the test result without retaining credentials.

The requested dedicated Earthdata **entry point** means an explicitly approved external authentication destination and managed credential handoff. For the current WAFIW client, this is an **outbound** dependency; it does not require exposing an inbound port, hosting an OAuth callback, or opening unrestricted inbound access on the Azure worker. A dedicated egress gateway is a deployment design option, not a requirement imposed by Earthdata.

## Local checkpoint: 9 October 2026

The local macOS test used:

```text
asf-search: 14.0.3
requests: 2.34.2
Endpoint: urs.earthdata.nasa.gov /oauth/tokens/user
HTTP status: 200
Authentication succeeded
```

Earlier token-validation attempts returned HTTP 403 and `ASFAuthenticationError`. The operator checked ASF authorization and accepted the missing EULA, then reported the successful result above. This sequence is consistent with an account/application prerequisite being resolved. It does not establish that every future 403 has the same cause.

The successful diagnostic explicitly disabled automatic `.netrc` lookup for that process. The browser account and the earlier `.netrc` account differed. `.netrc` interference was investigated, but disabling it alone still returned 403. Therefore it was not sufficient to resolve this incident.

**Established:** this local account/token could authenticate against Earthdata through ASF's client. **Still pending:** authenticated scene download, SNAP processing and a real Davis primary figure; Azure networking, secrets integration and scheduled execution have not been provisioned or tested. HTTP 200 at authentication is not proof of access to scene storage or a completed product.

## Account and application preparation

An authorized operator should complete these steps in their own browser:

1. Choose the Earthdata account that will own the operational credential. Establish its permitted institutional use, responsible owner and handover process before Azure deployment. Do not assume an Azure service identity is an Earthdata identity.
2. Sign into [ASF Vertex](https://search.asf.alaska.edu/) with that same Earthdata account.
3. Complete required ASF application authorization, profile attributes and applicable EULA acceptance.
4. In [Earthdata Login](https://urs.earthdata.nasa.gov/), check **Applications → Authorized Apps**. If necessary, use **Approve More Applications** and search for Alaska Satellite Facility. Review any requested agreements/attributes and authorize the appropriate application.
5. Generate a user token under **Generate Token**, copy the raw token, and arrange its secure transfer to the runtime secret store. Record its expiry separately from its secret value.

Earthdata documents application authorization and EULA acknowledgement as prerequisites when applicable. A successful login to the Earthdata website alone does not complete application authorization. Agreements belong to the selected Earthdata account; the operator must approve them, rather than having unattended jobs attempt acceptance.

Earthdata currently documents user tokens as valid for **60 days**, with at most **two valid tokens** per user. Plan renewal before the recorded expiry, validate the replacement, update the runtime secret and retire the old token as appropriate. Do not design a permanent unattended workflow around a token with no renewal owner.

## Network and OS/runtime requirements

Use FQDN-based controls appropriate to the Azure deployment rather than hardcoded public IP addresses. Azure Firewall HTTPS application rules match SNI; rules, routing, DNS and any corporate proxy must all permit the worker's requests. The following is an initial endpoint inventory, **not a complete verified production allowlist**:

| Destination | Purpose | Evidence / deployment action |
| --- | --- | --- |
| `urs.earthdata.nasa.gov:443` | Earthdata authentication and token validation | Required; `/oauth/tokens/user` returned 200 in the local ASF token test. Permit the SDK's required POST requests and legitimate redirects. |
| `cmr.earthdata.nasa.gov:443` | Catalogue requests from ASF search | ASF documents this as its default production CMR host. Verify the installed client's actual requests. |
| `datapool.asf.alaska.edu:443` | Sentinel-1 ZIP download | Both URLs in the repository's October 2021 Davis pair 0 use this host. Actual authenticated download remains pending. |
| Other ASF/data-storage redirect destinations | Delivery of selected products | Identify through one controlled download and review the required destinations before adding rules. Do not assume allowing Earthdata alone enables downloads. |
| The deployment's Azure Key Vault endpoint | Retrieval of the stored Earthdata token | Required if using the recommended Key Vault design; choose public restricted access or private endpoint/DNS according to the Azure architecture. |
| SNAP orbit/auxiliary-data services | Raw SAFE preprocessing | Separate dependency; discover and validate the configured SNAP installation's actual destinations during the one-scene test. |

The worker requires a maintained certificate trust store, accurate system time, functional DNS, the pinned/tested Python environment and suitable timeout/bandwidth/disk capacity for full scenes. If a corporate HTTPS inspection proxy is required, configure its approved CA trust in both Python/Requests and SNAP's Java runtime. **Do not disable TLS verification to make authentication work.**

Review proxy policy so it does not strip required authorization headers or log token-bearing request bodies. Explicitly configure permitted proxy and CA settings for the scheduled process. Environment variables such as `HTTPS_PROXY` and `REQUESTS_CA_BUNDLE` are deployment settings; they are not proof of working authentication.

The final allowlist must be validated from the actual Azure VM/container/job, using the same route, proxy, DNS, runtime account and secret source as production. Catalogue-only tests and tests against fully cached scene ZIPs do not exercise authenticated downloading.

## Credential delivery to the Azure job

Recommended design: store the Earthdata token as an **Azure Key Vault secret**, let the worker's managed identity retrieve that specific secret using appropriate least-privilege permissions, and inject it into the acquisition process as `EARTHDATA_TOKEN`. WAFIW already reads that variable; it does **not** currently implement Key Vault retrieval, managed-identity setup or token renewal. Those belong to the deployment launcher/orchestrator and remain to be implemented.

Azure managed identity authenticates to Azure resources such as Key Vault. It does not replace the NASA-issued token used to access Earthdata. Keep the Earthdata token out of YAML, Git, container images, notebook cells, shell command arguments and job logs.

Choose one credential method deliberately:

- With an explicit nonempty `EARTHDATA_TOKEN`, WAFIW selects token authentication. An invalid explicit token fails rather than falling back to another account.
- Without a token, WAFIW supports an explicit `urs.earthdata.nasa.gov` entry in the runtime user's standard `.netrc`. On POSIX, use private ownership and `chmod 600`.
- Requests/ASF may still consult `.netrc` independently of WAFIW's selection. For the validated token-only route, use a controlled service-account home and set `NETRC` to an empty credential file, or `os.devnull` for a process-level diagnostic. This prevents an unrelated/stale account overriding the intended credential, while preserving proxy/CA environment settings. Do not delete a developer's existing `.netrc`.

The OS service account/container must receive the secret in its own process environment. A variable exported in an administrator's interactive shell does not automatically reach a system service or scheduled job. Ensure logs, tracing and crash reporting do not dump process environments, Authorization headers, POST bodies or response cookies.

Hidden prompts were used initially for local entry; visible entry was then used to check the paste. Visible entry should be confined to a private local terminal and omitted from any shared screenshots/output. Production jobs must not require an interactive prompt. Supply the raw token without a `Bearer ` prefix or surrounding quotes.

## Acceptance test from the deployed worker

After the launcher has supplied `EARTHDATA_TOKEN`, run this diagnostic in the WAFIW environment. It performs real authentication locally on the worker; it does not print credential values or response bodies:

```bash
python - <<'PY'
import os
from importlib.metadata import version
from urllib.parse import urlsplit
import asf_search as asf

if not os.environ.get('EARTHDATA_TOKEN'):
    raise SystemExit('EARTHDATA_TOKEN is not available to this process')
os.environ['NETRC'] = os.devnull  # isolate this token-only diagnostic
print('asf-search:', version('asf-search'))
print('requests:', version('requests'))
session = asf.ASFSession()
original_request = session.request

def observed_request(method, url, **kwargs):
    response = original_request(method, url, **kwargs)
    endpoint = urlsplit(url)
    print('Endpoint:', endpoint.hostname, endpoint.path)
    print('HTTP status:', response.status_code)
    return response

session.request = observed_request
try:
    session.auth_with_token(os.environ['EARTHDATA_TOKEN'])
except Exception as error:
    print('Exception type:', type(error).__name__)
    raise SystemExit(1)
print('Authentication succeeded')
PY
```

Record the date, runtime/package versions, worker/network location, endpoint hostname/path and status. Do not record the token, raw HTTP bodies, signed URLs, headers or cookies. The exact endpoint is an observed SDK implementation detail and may change with SDK versions; repeat this test after dependency/network changes.

Then run one genuine, uncached Davis download and processing attempt with the same token-only credential policy supplied by the launcher:

```bash
python scripts/run_primary.py --config configs/davis.yaml run-catalog \
  --pairs examples/davis_catalog_202110/pairs.json \
  --pair-index 0 --max-pairs 1 --download
```

For a local interactive run, `scripts/run_with_earthdata_token.py` supplies both variables to the primary CLI child process; see the [installation command](installation.md#earthdata-download-authentication). The diagnostic's `NETRC` assignment is process-local and does not persist into the subsequent command. Configure `NETRC` separately in the launcher for the download too. Preserve existing valid downloads; use a reviewed fresh test root when an uncached test is required.

Deployment acceptance requires:

- Successful authentication from the job process.
- An authenticated download of a selected Sentinel-1 scene, with the required redirect destinations allowed.
- Successful SNAP preprocessing with orbit/auxiliary-data access and the reviewed DEM.
- A primary figure and provenance that refer to the real input scenes.
- A tested credential-replacement procedure and alerts for authentication/renewal failures.

`doctor` checks local file/executable presence. It does not check credentials, EULAs, Azure egress or the ability to download a scene. A model-free primary product remains segmentation only.

## Troubleshooting and ownership

| Observation | What to check next |
| --- | --- |
| DNS failure, connection timeout or TLS error | Worker DNS, route/firewall/proxy, certificate trust and system time; verify the request reaches the intended endpoint. |
| Earthdata HTTP 401 or 403 | Token validity, correct account, ASF application authorization, required profile fields/EULAs and credential interference. A status alone is not a unique diagnosis; a proxy can also return 403. |
| Authentication 200, scene download fails | Data-host/redirect access, account authorization for the requested data, storage, download response and cache/partial-file state. |
| Interactive login works, scheduled job fails | Job identity, home directory, secret injection, token expiry, proxy/CA settings and permissions. |
| WAFIW reports only a generic auth failure | Use the diagnostic above to distinguish request status from SDK exception type. Never enable unrestricted HTTP-body/header logging. |

Assign responsibility for account/EULA approval and token renewal to the application owner; Azure egress/DNS/proxy/trust to the platform/network owner; secret-store permissions/injection to the deployment owner; and scene/preprocessing/figure acceptance to the WAFIW operator. These are build and operational prerequisites, not ad hoc debugging tasks to discover after scheduling production jobs.

## Sources

- [Earthdata application authorization and EULAs](https://urs.earthdata.nasa.gov/documentation/for_users/what_is_app_auth)
- [Earthdata pre-authorization steps](https://urs.earthdata.nasa.gov/documentation/for_users/how_to_preauth_app)
- [Earthdata user-token management and expiry](https://urs.earthdata.nasa.gov/documentation/for_users/user_token)
- [ASF authentication methods](https://docs.asf.alaska.edu/asf_search/ASFSession/)
- [ASF best practices, CMR host and `.netrc` header precedence](https://docs.asf.alaska.edu/asf_search/BestPractices/)
- [ASF authentication troubleshooting](https://docs.asf.alaska.edu/api/troubleshooting/)
- [Azure Firewall rule processing and HTTPS/SNI matching](https://learn.microsoft.com/en-us/azure/firewall/rule-processing)
- [Azure Key Vault authentication](https://learn.microsoft.com/en-us/azure/key-vault/general/authentication)

See also [installation and coastline setup](installation.md) and [DEM preparation](dem_preparation.md).
