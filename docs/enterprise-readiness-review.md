# Enterprise Readiness Review

Questo documento rivaluta l'applicazione rispetto ai pattern dei player piu' forti della categoria e identifica cosa e' gia' stato recepito e cosa resta da completare.

## Pattern di mercato osservati

### Veza

Fonte ufficiale:

- https://veza.com/product/authorization-graph/

Pattern chiave:

- grafo autorizzativo unificato tra identita', macchine, applicazioni, permessi e dati
- risposta rapida a domande tipo "who can take what action on what data"
- modello piu' vicino a una control plane relazionale che a uno scanner statico

Recepito nell'app:

- motore explainable con path di accesso
- identity fabric cross-source
- supporto a fonti multiple locali, remote e importate offline

Gap residui:

- piu' connettori live enterprise validati su tenant reali
- persistence/search/analytics distribuiti su stack dedicato

### SailPoint

Fonte ufficiale:

- https://www.sailpoint.com/identity-library/sailpoint-vs-varonis-the-complete-guide

Pattern chiave:

- identity security platform unificata
- governance, lifecycle, compliance e automazione dei processi di access review
- forte orientamento a certification, approval, segregation of duties

Recepito nell'app:

- report amministrativi professionali
- motore di spiegazione e what-if
- base dati gia' pronta a diventare control plane operativo

Gap residui:

- access reviews workflow-native
- approvazioni, campagne, attestazioni e SoD policies
- lifecycle governance e remediation orchestrate

### Varonis

Fonte ufficiale:

- https://www.varonis.com/products/data-security-platform

Pattern chiave:

- data-centric security posture
- prioritizzazione dei rischi, esposizioni e stale access
- lettura molto aggressiva e veloce di ACL, esposizioni e permessi dati

Recepito nell'app:

- scansione reale filesystem Windows/Linux
- hotspot, risk score, broad access e reporting
- benchmark reali e caching incrementale per ridurre il costo di raccolta

Gap residui:

- usage analytics e stale entitlement detection basata su activity logs
- alerting operativo continuo

### Saviynt

Fonte ufficiale:

- https://saviynt.com/

Pattern chiave:

- converged identity cloud
- governance + PAM + cloud permissions
- automazione e AI sui processi di access governance

Recepito nell'app:

- modello unificato tra on-prem, filesystem, fonti offline e blueprint cloud
- base per collegare ruoli, permessi e deleghe in un unico grafo

Gap residui:

- workflow multi-step e approvazioni
- esecuzione remediation e attivazione/deattivazione accessi

### Semperis

Fonte ufficiale:

- https://www.semperis.com/platform/directory-services-protector/

Pattern chiave:

- protezione directory e privilegio
- change tracking, impatto delle modifiche e blast radius

Recepito nell'app:

- scenari what-if
- explainability dei path
- superfici directory/IAM gia' mappate a blueprint ufficiali

Gap residui:

- validazione runtime su directory enterprise reali
- detection continua di cambi critici su AD/Entra

## Cosa rende gia' forte questa applicazione

- lavora su dati reali dell'host, non solo su snapshot demo
- puo' fondere piu' fonti in un unico grafo
- usa report scaricabili adatti a contesti amministrativi e audit
- espone chiaramente stato, target, connettori e rischio
- la raccolta filesystem e' stata ottimizzata con parallelismo e cache incrementale
- supporta Windows, Linux e SSH senza dipendere da iscrizioni o servizi a pagamento

## Cosa manca per essere enterprise pieno

- tenanting reale per piu' organizzazioni con isolamento forte
- validazione live di `AD/LDAP`, `Microsoft Graph`, `Azure RBAC`, `Okta`, `CyberArk`
- stack di produzione esterno: `PostgreSQL`, `Neo4j`, `OpenSearch`, `ClickHouse`, `Valkey`
- bus eventi e workflow durevoli con `Kafka` e `Temporal`
- remediation guidate, approval chain, certification campaign e SoD
- remote Windows collector robusto via agent o `WinRM`
- HA, backup, disaster recovery e secret management centralizzato

## Valutazione netta

Lo stato attuale non e' piu' quello di una demo: e' una base concreta di piattaforma, soprattutto per controllo accessi filesystem e fusioni cross-source. Il salto da qui a "vero enterprise" non e' rifare il motore, ma completare governance, collector cloud validati e stack distribuito di produzione.
