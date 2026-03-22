# Official Integration Notes

Questo documento riassume le decisioni implementative della parte cloud e IAM sulla base delle documentazioni ufficiali dei sistemi target. Dove il runtime non e' ancora validato contro tenant reali, il comportamento e la modellazione restano comunque ancorati a sorgenti ufficiali.

## Microsoft Entra ID / Microsoft Graph

Punti chiave adottati:

- `transitiveMemberOf` resta il modo corretto per spiegare membership e nested groups lato server.
- le query avanzate su oggetti directory richiedono `ConsistencyLevel: eventual`.
- `delta query` va usata per i sync incrementali, con persistenza del token e fallback a full sync quando il token non e' piu' valido.
- `JSON batching` e' utile per contenere la latenza, ma va mantenuto entro il limite documentato di `20` richieste per batch.
- i `site-id` Graph di SharePoint sono identificatori composti che contengono gia' virgole; nel prodotto quindi vengono separati con `;` e non con `,`.

Impatto sul prodotto:

- il blueprint e il runtime distinguono chiaramente tra modello ufficiale completo e copertura runtime attuale
- il collector runtime usa batching per le espansioni `transitiveMemberOf`, ma dichiara ancora come gap aperto la persistenza dei token delta
- la parte SharePoint / Exchange viene trattata come superficie distinta, non come semplice appendice del collector Entra
- la raccolta SharePoint viene dichiarata opzionale e limitata ai `site-id` configurati esplicitamente

Fonti:

- https://learn.microsoft.com/en-us/graph/api/user-list-transitivememberof?view=graph-rest-1.0
- https://learn.microsoft.com/en-us/graph/delta-query-overview
- https://learn.microsoft.com/en-us/graph/json-batching

## Azure RBAC

Punti chiave adottati:

- i role assignments devono essere modellati per scope, non solo per principal
- la spiegazione dell'accesso deve mantenere esplicita l'ereditarieta' verso scope figli
- le role definitions vanno cache-ate separatamente dai role assignments
- `List For Scope` con `$filter=atScope()` restituisce solo le assegnazioni al livello corrente, quindi non basta a descrivere ereditarieta' verso o da scope superiori

Impatto sul prodotto:

- il motore materializza le assegnazioni come istanze di ruolo explainable
- il blueprint evidenzia che la copertura runtime attuale e' ancora parziale sui management groups e sulla discesa completa degli scope
- il runtime espone esplicitamente che oggi la raccolta e' subscription-first e non sostituisce ancora un crawl completo della gerarchia di management groups

Fonti:

- https://learn.microsoft.com/en-us/azure/role-based-access-control/role-assignments
- https://learn.microsoft.com/en-us/rest/api/authorization/role-assignments/list-for-scope?view=rest-authorization-2022-04-01

## SharePoint Online / Exchange Online

Punti chiave adottati:

- le permissioni SharePoint vanno raccolte a livello site con piena consapevolezza dei limiti documentati dell'API
- le mailbox permissions richiedono una vista Exchange dedicata, non vanno dedotte solo da Graph
- la copertura SharePoint non sostituisce selected permissions, inheritance profondi e tutte le varianti Exchange

Impatto sul prodotto:

- `m365-collaboration` resta un collector distinto
- il runtime corrente lo espone come blueprint-only per non fingere copertura live che oggi non c'e'

Fonti:

- https://learn.microsoft.com/en-us/graph/api/site-list-permissions?view=graph-rest-1.0
- https://learn.microsoft.com/en-us/powershell/module/exchange/get-mailboxpermission?view=exchange-ps

## Active Directory / LDAP

Punti chiave adottati:

- per membership transitiva on-prem e' preferibile spingere la risoluzione nel directory server
- `LDAP_MATCHING_RULE_IN_CHAIN` e' una primitive specifica di Active Directory, non LDAP generico
- l'ereditarieta' ACL va mantenuta nel modello, non appiattita senza spiegazione
- quando il directory endpoint non supporta la matching rule, il prodotto deve dichiarare fallback a `memberOf` diretto invece di dare per scontata la closure completa

Impatto sul prodotto:

- il blueprint distingue chiaramente directory identity e fonti ACL
- il runtime prova la matching rule in chain e fa fallback esplicito a `memberOf` diretto se il server non la supporta
- il runtime segnala come parziale la copertura LDAP corrente, perche' oggi raccoglie bene identita' e membership ma non sostituisce tutta la modellazione ACL enterprise on-prem

Fonti:

- https://learn.microsoft.com/en-us/windows/win32/adsi/search-filter-syntax
- https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/4e638665-f466-4597-93c4-12f2ebfabab5

## Okta

Punti chiave adottati:

- le letture vanno guidate dalla paginazione tramite `Link header`
- la ricerca e' documentata come eventualmente consistente, quindi serve reconciliation prima di consolidare stato autorevole
- la `List all users` standard non restituisce gli utenti `DEPROVISIONED`, quindi la copertura del lifecycle va dichiarata come incompleta se non esiste un pass dedicato

Impatto sul prodotto:

- il collector runtime usa paginazione guidata da `Link`
- il blueprint continua a considerare parziale la copertura runtime, perche' non include ancora assegnazioni applicative, overlay entitlement piu' avanzati e una reconciliation dei `DEPROVISIONED`

Fonti:

- https://developer.okta.com/docs/api/openapi/okta-management/management/tag/Group/
- https://developer.okta.com/docs/api/openapi/okta-management/management/tag/UserResources/

## CyberArk

Punti chiave adottati:

- le integrazioni privilegiate devono essere isolate dalle workforce identities
- expiry, ticket metadata e break-glass memberships vanno trattati come primitive di primo livello nel modello

Impatto sul prodotto:

- il collector runtime copre membership e permission flag dei safe
- il blueprint espone come gap ancora aperti expiry, ticket metadata e responder overlays

Fonti:

- https://api-docs.cyberark.com/
- https://api-docs.cyberark.com/docs/siem-and-utilities/secure-infrastructure-access

## AWS IAM / Organizations

Punti chiave adottati:

- l'inventario degli account (`Organizations`) e l'inventario delle identita' (`IAM`) sono superfici diverse e vanno mantenute distinte
- l'analisi efficace dei permessi richiede non solo attachment di policy ma anche simulazione task-oriented
- le API `IAM` usano `Marker` / `IsTruncated`, mentre `Organizations` usa `NextToken`; i due cicli di paginazione non vanno confusi

Impatto sul prodotto:

- il blueprint `aws-iam` modella account, utenti, ruoli, policy e simulazione
- il runtime lo espone come blueprint-only fino a quando non verra' cablato un collector live account-aware

Fonti:

- https://docs.aws.amazon.com/IAM/latest/APIReference/API_ListUsers.html
- https://docs.aws.amazon.com/IAM/latest/APIReference/API_ListGroupsForUser.html
- https://docs.aws.amazon.com/IAM/latest/APIReference/API_SimulatePrincipalPolicy.html
- https://docs.aws.amazon.com/organizations/latest/APIReference/API_ListAccounts.html

## Google Workspace / Cloud Identity / Drive

Punti chiave adottati:

- la directory (`users`, `groups`, `members`) e le permissioni Drive sono superfici da modellare separatamente
- la raccolta enterprise tipica richiede domain-wide delegation verso un subject amministrativo
- per Drive i crawl condivisi devono restare shared-drive aware, con `supportsAllDrives` e scopi/corpora espliciti

Impatto sul prodotto:

- `google-directory` e `google-drive-collaboration` sono blueprint dedicati e distinti
- il prodotto chiarisce che una directory Google da sola non spiega i permessi Drive
- il runtime valida gia' che il service account JSON e il subject amministrativo abbiano una forma coerente prima di considerare il connector configurato

Fonti:

- https://developers.google.com/workspace/admin/directory/reference/rest/v1/users/list
- https://developers.google.com/workspace/admin/directory/reference/rest/v1/groups/list
- https://developers.google.com/workspace/admin/directory/reference/rest/v1/members/list
- https://developers.google.com/workspace/drive/api/reference/rest/v3/permissions/list
