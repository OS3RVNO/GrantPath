/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

export type LocaleCode = 'en' | 'it' | 'de' | 'fr' | 'es'

type TranslationTable = Record<string, string>

type DynamicRule = {
  pattern: RegExp
  render: (...groups: string[]) => string
}

type I18nValue = {
  locale: LocaleCode
  setLocale: (locale: LocaleCode) => void
  t: (source: string, params?: Record<string, string | number | null | undefined>) => string
  formatDateTime: (value?: string | null) => string
  formatDate: (value?: string | null) => string
  languageOptions: Array<{ code: LocaleCode; label: string }>
}

const STORAGE_KEY = 'eip.locale'

const translations: Record<LocaleCode, TranslationTable> = {
  en: {},
  it: {
    Language: 'Lingua',
    English: 'Inglese',
    Italian: 'Italiano',
    German: 'Tedesco',
    French: 'Francese',
    Spanish: 'Spagnolo',
    Home: 'Home',
    Investigate: 'Analizza',
    Govern: 'Governance',
    Sources: 'Sorgenti',
    Operations: 'Operazioni',
    Explain: 'Spiega',
    Exposure: 'Esposizione',
    'What-If': 'What-If',
    Reviews: 'Revisioni',
    Remediation: 'Remediation',
    Auth: 'Autenticazione',
    Collection: 'Raccolta',
    Imports: 'Importazioni',
    Identity: 'Identita',
    Status: 'Stato',
    Platform: 'Piattaforma',
    Audit: 'Audit',
    'Support Matrix': 'Matrice di supporto',
    'Operational trust per connector surface': 'Affidabilita operativa per superficie di connettore',
    supported: 'supportati',
    pilot: 'pilot',
    blueprints: 'blueprint',
    Evidence: 'Evidenze',
    'Current gaps': 'Gap correnti',
    'Next action': 'Prossima azione',
    Supported: 'Supportato',
    'Pilot ready': 'Pronto per pilot',
    Experimental: 'Sperimentale',
    'Runtime verified': 'Verificato a runtime',
    'Config validated': 'Configurazione validata',
    'Documentation aligned': 'Allineato alla documentazione',
    Planned: 'Pianificato',
    Production: 'Produzione',
    Pilot: 'Pilot',
    Lab: 'Laboratorio',
    'Design only': 'Solo design',
    'Native runtime': 'Runtime nativo',
    'Identity and directory': 'Identita e directory',
    'Cloud control plane': 'Control plane cloud',
    Collaboration: 'Collaborazione',
    'Privileged access': 'Accesso privilegiato',
    'Other enterprise': 'Altro enterprise',
    'Job Center': 'Centro lavori',
    'Background work and worker lanes': 'Lavoro in background e corsie worker',
    'Worker lanes': 'Corsie worker',
    'Recent jobs': 'Job recenti',
    'Report delivery': 'Consegna report',
    'Scheduler enabled': 'Scheduler attivo',
    'Scheduler manual': 'Scheduler manuale',
    'Last completed: {value}': 'Ultimo completamento: {value}',
    'Next due: {value}': 'Prossima esecuzione: {value}',
    'Last status: {value}': 'Ultimo stato: {value}',
    'Background work becomes visible after administrator authentication.':
      "Il lavoro in background diventa visibile dopo l'autenticazione dell'amministratore.",
    '{count} queued': '{count} in coda',
    '{count} work items': '{count} elementi di lavoro',
    Navigation: 'Navigazione',
    'Section Menu': 'Menu sezione',
    'Open a module': 'Apri un modulo',
    'Universal search': 'Ricerca universale',
    'Search users, groups, roles, folders, mailboxes, vaults...':
      'Cerca utenti, gruppi, ruoli, cartelle, mailbox, vault...',
    'who • why • what if': 'chi • perche • what if',
    'Searching the graph...': 'Ricerca nel grafo...',
    'No matching identity or resource.': 'Nessuna identita o risorsa corrispondente.',
    'Select a user or resource to update the live access views.':
      'Seleziona un utente o una risorsa per aggiornare le viste live degli accessi.',
    'Command Center': 'Command Center',
    'Start from the shortest path to action': "Parti dal percorso piu breve verso l'azione",
    'Use this home to monitor the platform quickly, then jump into the specific workspace only when you need to investigate, govern, manage sources or review operations.':
      'Usa questa home per monitorare rapidamente la piattaforma, poi apri il workspace specifico solo quando devi analizzare, governare, gestire le sorgenti o verificare le operazioni.',
    'Answer who has access and why': 'Rispondi a chi ha accesso e perche',
    'Run reviews and export evidence': 'Esegui revisioni ed esporta evidenze',
    'Manage auth, targets and imports': 'Gestisci autenticazione, target e importazioni',
    'Track scan health and platform posture': 'Monitora salute delle scansioni e postura della piattaforma',
    'MVP Readiness': 'Prontezza MVP',
    'What still needs attention': 'Cosa richiede ancora attenzione',
    complete: 'completato',
    ready: 'pronto',
    'Selected Step': 'Passo selezionato',
    required: 'obbligatorio',
    recommended: 'consigliato',
    'Recommended action: {value}': 'Azione consigliata: {value}',
    'Data freshness: {value}': 'Freschezza dei dati: {value}',
    'Open relevant section': 'Apri la sezione rilevante',
    'Blockers: {value}': 'Blocchi: {value}',
    'MVP readiness becomes available after the first authenticated refresh.':
      "La prontezza MVP diventa disponibile dopo il primo refresh autenticato.",
    'Top Exposure': 'Esposizione principale',
    'Most exposed resources': 'Risorse piu esposte',
    'Materialized analytics': 'Analytics materializzate',
    'Exposure summaries': 'Summary di esposizione',
    'Top exposed resources': 'Risorse piu esposte',
    'Materialized summaries from the resource exposure index.':
      "Summary materializzate dall'indice di esposizione delle risorse.",
    'Top exposed principals': 'Principali piu esposti',
    'Materialized summaries from the principal access index.':
      "Summary materializzate dall'indice di accesso dei principali.",
    'No exposure hotspot is available yet.': 'Nessun hotspot di esposizione disponibile.',
    'Suggested Actions': 'Azioni suggerite',
    'What deserves attention now': 'Cosa richiede attenzione adesso',
    'No operator insight is available yet.': 'Nessun insight operativo disponibile.',
    'Recent Trend': 'Trend recente',
    'Privilege drift snapshot': 'Snapshot della deriva dei privilegi',
    'Question Studio': 'Question Studio',
    'Why does this access exist?': 'Perche esiste questo accesso?',
    Principal: 'Principale',
    Resource: 'Risorsa',
    Permissions: 'Permessi',
    Paths: 'Percorsi',
    Complexity: 'Complessita',
    Risk: 'Rischio',
    'Select a resource from the catalog to materialize the explain path.':
      'Seleziona una risorsa dal catalogo per materializzare il percorso di explain.',
    'No effective access path is currently materialized for this principal-resource pair. Try another resource or switch to Exposure to inspect who currently reaches the resource.':
      'Al momento non esiste un percorso di accesso effettivo materializzato per questa coppia principale-risorsa. Prova un\'altra risorsa o passa a Esposizione per vedere chi la raggiunge.',
    'Loading graph view...': 'Caricamento vista grafo...',
    'Open investigation graph': 'Apri grafo investigativo',
    'Hide investigation graph': 'Nascondi grafo investigativo',
    Density: 'Densita',
    Compact: 'Compatto',
    Expanded: 'Esteso',
    'Loading current page...': 'Caricamento pagina corrente...',
    'Loading access window...': 'Caricamento finestra accessi...',
    'This investigation graph is currently capped to {nodes} nodes and {edges} links so the view stays responsive.':
      'Questo grafo investigativo e limitato a {nodes} nodi e {edges} collegamenti per mantenere la vista reattiva.',
    'Who Has Access': 'Chi ha accesso',
    privileged: 'privilegiati',
    'What If': 'What If',
    'Blast radius simulation': 'Simulazione del blast radius',
    'Change to simulate': 'Cambiamento da simulare',
    'Focus resource': 'Risorsa in focus',
    'Scenario reasoning not available.': 'Ragionamento dello scenario non disponibile.',
    'Impacted principals': 'Principali impattati',
    'Impacted resources': 'Risorse impattate',
    'Removed paths': 'Percorsi rimossi',
    'Privileged removed': 'Privilegi rimossi',
    'Delta principals': 'Principali delta',
    'Delta resources': 'Risorse delta',
    'Delta pairs': 'Coppie delta',
    'Loading simulation view...': 'Caricamento vista simulazione...',
    'Focused Entity': 'Entita focalizzata',
    'No entity selected': 'Nessuna entita selezionata',
    Kind: 'Tipo',
    Criticality: 'Criticita',
    'Why this matters': 'Perche conta',
    Signals: 'Segnali',
    'Privilege drift over recent scans': 'Deriva dei privilegi nelle scansioni recenti',
    Insights: 'Insight',
    'Operator notes': 'Note operative',
    'No graph to render for this access path.':
      'Nessun grafo da renderizzare per questo percorso di accesso.',
    'Access Map': 'Mappa di accesso',
    'Clean path view for the selected entitlement':
      "Vista pulita del percorso per l'autorizzazione selezionata",
    'Each lane shows the effective route from identity to resource, with one transition per step.':
      "Ogni corsia mostra il percorso effettivo dall'identita alla risorsa, con una transizione per passo.",
    Nodes: 'Nodi',
    Links: 'Collegamenti',
    Pipeline: 'Pipeline',
    'Index refresh': 'Refresh degli indici',
    'Path {index}': 'Percorso {index}',
    'risk {value}': 'rischio {value}',
    'Showing the top {visible} paths out of {total} to keep the view readable.':
      'Mostro i primi {visible} percorsi su {total} per mantenere la vista leggibile.',
    'Run a scenario to render blast radius.': 'Esegui uno scenario per visualizzare il blast radius.',
    Mode: 'Modalita',
    'Reused rows': 'Righe riutilizzate',
    'Recomputed rows': 'Righe ricalcolate',
    'Group closure refresh': 'Refresh della chiusura gruppi',
    'Hierarchy refresh': 'Refresh della gerarchia',
    'Carry-forward': 'Riutilizzo',
    Existing: 'Esistente',
    Delta: 'Delta',
    'Full rebuild': 'Ricostruzione completa',
    'Previous snapshot: {value}': 'Snapshot precedente: {value}',
    'The next successful scan will publish an index refresh summary.':
      'La prossima scansione riuscita pubblichera un riepilogo del refresh degli indici.',
    'Access index refresh uses carry-forward when the graph is unchanged and delta recomputation when the impacted scope stays small.':
      "Il refresh dell'indice di accesso riutilizza lo stato precedente quando il grafo non cambia e usa la ricomputazione delta quando il perimetro impattato resta piccolo.",
    Rows: 'Righe',
    Previous: 'Precedente',
    Next: 'Successivo',
    'No effective principals for this resource.': 'Nessun principale effettivo per questa risorsa.',
    '{count} effective principals': '{count} principali effettivi',
    '{count} principals': '{count} principali',
    '{count} privileged': '{count} privilegiati',
    '{count} resources': '{count} risorse',
    'Showing {start}-{end}': 'Mostro {start}-{end}',
    user: 'utente',
    'service account': 'account di servizio',
    group: 'gruppo',
    role: 'ruolo',
    resource: 'risorsa',
    'Executive command center': 'Command center esecutivo',
    'Focus on access questions': 'Concentrati sulle domande di accesso',
    'Run reviews and remediation': 'Gestisci revisioni e remediation',
    'Manage identities and collection': 'Gestisci identita e raccolta',
    'Track readiness and performance': 'Monitora prontezza e prestazioni',
    'Current Focus': 'Focus corrente',
    'Executive Output': 'Output executive',
    'Download a polished report for the selected principal, resource and scenario.':
      'Scarica un report curato per il principale, la risorsa e lo scenario selezionati.',
    'Download PDF': 'Scarica PDF',
    'Export Excel': 'Esporta Excel',
    'Open HTML': 'Apri HTML',
    'Scan enabled targets': 'Scansiona i target attivi',
    'Scanning...': 'Scansione...',
    Logout: 'Esci',
    'Signing out...': 'Disconnessione...',
    'Production-facing control plane for live filesystem access, explainable paths and operator-ready reporting.':
      'Control plane orientato alla produzione per accessi filesystem live, percorsi spiegabili e reporting operativo.',
    'Admin session: {value}': 'Sessione admin: {value}',
    'Host: {value}': 'Host: {value}',
    'Snapshot: {value}': 'Snapshot: {value}',
    'Targets active: {value}': 'Target attivi: {value}',
    'Scheduler: manual': 'Scheduler: manuale',
    'Scheduler: every {value}s': 'Scheduler: ogni {value}s',
    'Password Rotation Required': 'Rotazione password richiesta',
    'Rotate the bootstrap administrator password':
      "Ruota la password dell'amministratore bootstrap",
    'This deployment keeps the workspace locked until the first-run administrator secret is replaced with a permanent password.':
      "Questa installazione mantiene il workspace bloccato finche il segreto iniziale dell'amministratore non viene sostituito con una password permanente.",
    Administrator: 'Amministratore',
    'Security gate': 'Blocco di sicurezza',
    'Workspace access locked': 'Accesso al workspace bloccato',
    Workspace: 'Workspace',
    'Workspace: {value}': 'Workspace: {value}',
    'Organizations and environments': 'Organizzazioni e ambienti',
    'Use dedicated workspaces to isolate a customer, business unit or environment while keeping authentication and platform administration in one control plane.':
      'Usa workspace dedicati per isolare un cliente, una business unit o un ambiente mantenendo autenticazione e amministrazione della piattaforma nello stesso control plane.',
    'Update active workspace': 'Aggiorna il workspace attivo',
    'Workspace name': 'Nome workspace',
    'Save workspace details': 'Salva dettagli workspace',
    'Create workspace': 'Crea workspace',
    'Workspace activated. The control plane has been refreshed.':
      'Workspace attivato. Il control plane e stato aggiornato.',
    'Workspace created. Switch to it when you are ready to isolate another organization or environment.':
      'Workspace creato. Passaci quando sei pronto a isolare un altra organizzazione o ambiente.',
    'Workspace details updated.': 'Dettagli del workspace aggiornati.',
    'Unable to activate the workspace.': 'Impossibile attivare il workspace.',
    'Unable to create the workspace.': 'Impossibile creare il workspace.',
    'Unable to update the workspace.': 'Impossibile aggiornare il workspace.',
    Slug: 'Slug',
    'On-prem': 'On-prem',
    Hybrid: 'Ibrido',
    Cloud: 'Cloud',
    'Current password': 'Password attuale',
    'New password': 'Nuova password',
    'Updating...': 'Aggiornamento...',
    'Rotate password': 'Ruota password',
    'Sign out': 'Esci',
    Password: 'Password',
    'Password provider': 'Provider password',
    'Local application account': 'Account locale applicazione',
    'Signing in...': 'Accesso in corso...',
    'Sign in with domain credentials': 'Accedi con credenziali di dominio',
    'Sign in as application administrator': "Accedi come amministratore dell'applicazione",
    'Authentication': 'Autenticazione',
    'Sign-in providers': 'Provider di accesso',
    'Local admin MFA': 'MFA admin locale',
    'Built-in TOTP for local application administrators':
      'TOTP integrato per gli amministratori locali dell\'applicazione',
    'Provider-managed authentication': 'Autenticazione gestita dal provider',
    enabled: 'abilitata',
    'provider-managed': 'gestita dal provider',
    'Local administrators can use built-in TOTP MFA. Keycloak is optional and can enforce MFA upstream when configured as an OIDC provider.':
      "Gli amministratori locali possono usare la MFA TOTP integrata. Keycloak e opzionale e puo imporre MFA a monte se configurato come provider OIDC.",
    'Preparing...': 'Preparazione...',
    'Re-generate setup': 'Rigenera setup',
    'Enable MFA': 'Abilita MFA',
    'Manual setup key': 'Chiave di setup manuale',
    'Authenticator code': 'Codice autenticatore',
    'Enabling...': 'Abilitazione...',
    'Confirm MFA': 'Conferma MFA',
    'Current TOTP code': 'Codice TOTP corrente',
    'Disabling...': 'Disabilitazione...',
    'Disable MFA': 'Disabilita MFA',
    'Password sign-in': 'Accesso con password',
    'Browser redirect': 'Redirect browser',
    Disable: 'Disabilita',
    Enable: 'Abilita',
    Remove: 'Rimuovi',
    'Provider name': 'Nome provider',
    Type: 'Tipo',
    Preset: 'Preset',
    'OAuth2 / OIDC': 'OAuth2 / OIDC',
    'LDAP / Domain': 'LDAP / Dominio',
    'LDAP server URI': 'URI server LDAP',
    'Base DN': 'Base DN',
    'Service bind DN': 'Service bind DN',
    'Bind secret env var': 'Variabile env del segreto bind',
    'Allowed groups': 'Gruppi consentiti',
    'Issuer URL': 'Issuer URL',
    'Discovery URL': 'Discovery URL',
    'Client ID': 'Client ID',
    'Client secret env var': 'Variabile env del client secret',
    'Allowed email domains': 'Domini email consentiti',
    'Allowed email addresses': 'Indirizzi email consentiti',
    Scopes: 'Scope',
    Description: 'Descrizione',
    'Create provider': 'Crea provider',
    'Active': 'Attivo',
    Configured: 'Configurato',
    Attention: 'Attenzione',
    Disabled: 'Disabilitato',
    Optional: 'Opzionale',
    Healthy: 'Salute OK',
    Watch: 'Da controllare',
    Critical: 'Critico',
    Info: 'Info',
    'Live collector': 'Collector live',
    'Partial runtime': 'Runtime parziale',
    'Blueprint only': 'Solo blueprint',
    Auto: 'Auto',
    'SSH remote': 'SSH remoto',
    'Local path': 'Percorso locale',
    Keep: 'Mantieni',
    Revoke: 'Revoca',
    'Follow up': 'Follow up',
    Pending: 'In attesa',
    'n/d': 'n/d',
    disabled: 'disabilitato',
    completed: 'completato',
    warning: 'attenzione',
    idle: 'inattivo',
    Freshness: 'Freschezza',
    Scope: 'Ambito',
    Action: 'Azione',
    Progress: 'Progresso',
    'privileged principals': 'principali privilegiati',
    'delegated paths': 'percorsi delegati',
    'Selected resource': 'Risorsa selezionata',
    principals: 'principali',
    'Why this entity matters': 'Perche questa entita conta',
    'How criticality is interpreted': 'Come viene interpretata la criticita',
    'Criticality is the business importance score assigned by the normalization pipeline. Higher values usually indicate entities tied to sensitive resources, privileged routes or important operational scope.':
      'La criticita e il punteggio di importanza business assegnato dalla pipeline di normalizzazione. Valori piu alti indicano in genere entita legate a risorse sensibili, percorsi privilegiati o ambiti operativi importanti.',
    'Why the risk score is elevated': 'Perche il punteggio di rischio e elevato',
    'Risk is derived from effective permissions, privilege indicators, indirect grant paths and breadth of exposure. It is meant to explain urgency, not hide it behind a black-box score.':
      'Il rischio deriva dai permessi effettivi, dagli indicatori di privilegio, dai percorsi indiretti di grant e dall ampiezza dell esposizione. Serve a spiegare l urgenza, non a nasconderla dietro un punteggio opaco.',
    'Select any entity to inspect its neighborhood.':
      'Seleziona un entita per ispezionarne il contesto.',
    'Saving...': 'Salvataggio...',
    'Add sign-in provider': 'Aggiungi provider di accesso',
    'Monitored Targets': 'Target monitorati',
    'Filesystem scope': 'Ambito filesystem',
    'depth {value}': 'profondita {value}',
    '{value} entries': '{value} elementi',
    'Scan now': 'Scansiona ora',
    'Target name': 'Nome target',
    'Filesystem path': 'Percorso filesystem',
    Connection: 'Connessione',
    'Local / mounted': 'Locale / montato',
    'Remote Linux via SSH': 'Linux remoto via SSH',
    'SSH host': 'Host SSH',
    'SSH username': 'Utente SSH',
    Port: 'Porta',
    'Password env var': 'Variabile env password',
    'Private key path': 'Percorso chiave privata',
    'Max depth': 'Profondita massima',
    'Max entries': 'Elementi massimi',
    'Local mode covers host paths, mounted volumes and UNC shares reachable by the server. SSH mode is designed for remote Linux targets. Linux collectors read POSIX ACLs with getfacl when available.':
      'La modalita locale copre percorsi host, volumi montati e share UNC raggiungibili dal server. La modalita SSH e pensata per target Linux remoti. I collector Linux leggono le ACL POSIX con getfacl quando disponibile.',
    'Adding...': 'Aggiunta...',
    'Add monitored target': 'Aggiungi target monitorato',
    'Latest Scan': 'Ultima scansione',
    'Operational status': 'Stato operativo',
    Finished: 'Completato',
    Duration: 'Durata',
    Warnings: 'Avvisi',
    'No live scan recorded yet.': 'Nessuna scansione live registrata al momento.',
    Governance: 'Governance',
    'Access reviews': 'Revisioni accessi',
    '{value} pending': '{value} in attesa',
    '{value} revoke': '{value} da revocare',
    'Review campaign name': 'Nome campagna di review',
    'Min risk': 'Rischio minimo',
    'Max items': 'Elementi massimi',
    'Only include privileged effective access': 'Includi solo accessi effettivi privilegiati',
    'Generating...': 'Generazione...',
    'Create review campaign': 'Crea campagna di review',
    Items: 'Elementi',
    Snapshot: 'Snapshot',
    'Create or select a campaign to review high-risk access with deterministic decisions.':
      'Crea o seleziona una campagna per revisionare accessi ad alto rischio con decisioni deterministiche.',
    'Deterministic change plan': 'Piano di modifica deterministico',
    'Open a remediation plan from any review item to see a staged and explainable change path.':
      'Apri un piano di remediation da un elemento della review per vedere un percorso di modifica graduale e spiegabile.',
    'Export current review': 'Esporta review corrente',
    'Running benchmark...': 'Benchmark in esecuzione...',
    'Refresh benchmark': 'Aggiorna benchmark',
    'Run benchmark': 'Esegui benchmark',
    'Workspace sections': 'Sezioni del workspace',
    'Investigation graph': 'Grafo investigativo',
    'Dense neighborhood view for the focused entity':
      'Vista densa del vicinato per l entita focalizzata',
    'Use the dense graph to inspect nearby grants, memberships and inherited routes without collapsing everything into a single path.':
      'Usa il grafo denso per ispezionare grant vicini, membership e percorsi ereditati senza comprimere tutto in un unico path.',
    'No investigation graph is available for this focus yet.':
      'Non e disponibile ancora un grafo investigativo per questo focus.',
    'Start from a short operational dashboard with top exposure, quick actions and recent platform signals before drilling into a workflow.':
      'Parti da una dashboard operativa compatta con esposizione principale, azioni rapide e segnali recenti della piattaforma prima di entrare in un workflow.',
    'Use the explain, exposure and what-if views to answer who has access, why it exists and what changes would do.':
      'Usa le viste explain, exposure e what-if per capire chi ha accesso, perche esiste e cosa cambierebbe con una modifica.',
    'Keep decisions, revoke plans and review evidence together so the governance loop stays clear and deterministic.':
      'Tieni insieme decisioni, piani di revoca ed evidenze di review per mantenere il ciclo di governance chiaro e deterministico.',
    'Configure administrators, sign-in providers, monitored targets, offline bundles and cross-source identity linking in one place.':
      'Configura amministratori, provider di accesso, target monitorati, bundle offline e collegamento identita cross-source in un solo posto.',
    'Monitor scan health, runtime posture, connector readiness, benchmarks and administrator activity without cluttering the investigation flow.':
      'Monitora salute delle scansioni, postura runtime, prontezza dei connettori, benchmark e attivita amministrativa senza sporcare il flusso investigativo.',
    'Offline Sources': 'Sorgenti offline',
    'Import local JSON bundles': 'Importa bundle JSON locali',
    'Identity Fabric': 'Identity Fabric',
    'Cross-source linked identities': 'Identita collegate cross-source',
    'Combined access footprint': 'Impronta di accesso combinata',
    '{count} linked identities | {permissions}': '{count} identita collegate | {permissions}',
    'Connect at least two identity sources for the same organization to unlock cross-source correlation and a unified user footprint.':
      'Collega almeno due sorgenti identita della stessa organizzazione per sbloccare la correlazione cross-source e una vista utente unificata.',
    'confidence {value}': 'confidenza {value}',
    Performance: 'Prestazioni',
    'Real local benchmark': 'Benchmark locale reale',
    'Running...': 'Esecuzione...',
    Targets: 'Target',
    'Run the live benchmark on demand so normal workspace loading stays fast.':
      'Esegui il benchmark live solo su richiesta, cosi il caricamento normale del workspace resta veloce.',
    'Official Blueprint': 'Blueprint ufficiale',
    'Cloud and IAM integration notes': 'Note di integrazione cloud e IAM',
    Runtime: 'Runtime',
    Limitation: 'Limitazione',
    'Official documentation': 'Documentazione ufficiale',
    'Audit Trail': 'Audit trail',
    'Recent administrator actions': 'Azioni recenti degli amministratori',
    'No audit event has been recorded yet.': 'Nessun evento di audit registrato al momento.',
    'Platform posture becomes available after administrator authentication.':
      "La postura della piattaforma diventa disponibile dopo l'autenticazione dell'amministratore.",
    '{kind} discovered from {source} in the {environment} estate.':
      '{kind} rilevato da {source} nell ambiente {environment}.',
    '{count} inbound relationships reference this entity.':
      '{count} relazioni in ingresso fanno riferimento a questa entita.',
    '{count} outbound relationships originate from this entity.':
      '{count} relazioni in uscita originano da questa entita.',
    'Observed tags: {value}.': 'Tag osservati: {value}.',
    'No extra classification tags were attached.': 'Non sono stati associati tag di classificazione aggiuntivi.',
    'Current score: {value}.': 'Punteggio attuale: {value}.',
    'Current classification signals: {value}.': 'Segnali di classificazione correnti: {value}.',
    'Current classification is based on the entity profile only.':
      'La classificazione corrente si basa solo sul profilo dell entita.',
    'Owner context: {value}.': 'Contesto owner: {value}.',
    'No explicit owner was recorded for this entity.':
      'Per questa entita non e stato registrato alcun owner esplicito.',
    'Current risk score: {value}.': 'Punteggio di rischio attuale: {value}.',
    '{inbound} inbound and {outbound} outbound relationships contribute to the current exposure graph.':
      '{inbound} relazioni in ingresso e {outbound} in uscita contribuiscono al grafo di esposizione corrente.',
    'Important context: {value}.': 'Contesto importante: {value}.',
    'No special tags amplified the risk context for this entity.':
      'Nessun tag speciale ha amplificato il contesto di rischio per questa entita.',
    'avg {average} ms | p95 {p95} ms': 'media {average} ms | p95 {p95} ms',
    '{count} runs': '{count} esecuzioni',
    'Enterprise posture': 'Postura enterprise',
    Storage: 'Storage',
    Search: 'Ricerca',
    Cache: 'Cache',
    Analytics: 'Analytics',
    connected: 'connesso',
    'not connected': 'non connesso',
    'Operational details': 'Dettagli operativi',
    'Operational Flow': 'Flusso operativo',
    'Readiness and next actions': 'Prontezza e prossime azioni',
    'Overall status': 'Stato complessivo',
    Completion: 'Completamento',
    'Open actions': 'Azioni aperte',
    Ready: 'Pronto',
    'Recommended next actions': 'Prossime azioni consigliate',
    'Operational readiness is calculated after authentication.':
      "La prontezza operativa viene calcolata dopo l'autenticazione.",
    Connectors: 'Connettori',
    'Official integration posture': 'Postura ufficiale delle integrazioni',
    '{count} entities': '{count} entita',
    '{count} links': '{count} collegamenti',
    'Supported entities': 'Entita supportate',
    'Required environment': 'Ambiente richiesto',
    'Required permissions': 'Permessi richiesti',
    'Linked identities': 'Identita collegate',
    'Load JSON file': 'Carica file JSON',
    'Bundle JSON': 'Bundle JSON',
    'Importing...': 'Importazione...',
    'Import local source': 'Importa sorgente locale',
    'Risk Dashboard': 'Dashboard rischio',
    'Top risk findings': 'Principali finding di rischio',
    'No risk finding is available yet.': 'Nessun finding di rischio disponibile al momento.',
    'Hidden Admin Rights': 'Diritti admin nascosti',
    'Indirect privileged paths': 'Percorsi privilegiati indiretti',
    Findings: 'Finding',
    'No hidden admin right is currently flagged.':
      'Al momento non sono segnalati diritti admin nascosti.',
    'Recently Changed Access': 'Accessi modificati di recente',
    'Latest processing events': 'Ultimi eventi di elaborazione',
    'No recent platform change is available yet.':
      'Nessun cambiamento recente della piattaforma disponibile.',
    'Access Overview': 'Panoramica accessi',
    'Grants and paths': 'Grant e percorsi',
    'Risk Findings': 'Finding di rischio',
    'Change History': 'Storico modifiche',
    'User view': 'Vista utente',
    'Resource view': 'Vista risorsa',
    'Direct Grants': 'Grant diretti',
    'Inherited Grants': 'Grant ereditati',
    'Group Paths': 'Percorsi di gruppo',
    'Role Paths': 'Percorsi di ruolo',
    'Admin Rights': 'Diritti amministrativi',
    'No direct grant is currently modeled for this entity.':
      'Al momento non e modellato alcun grant diretto per questa entita.',
    'No inherited grant is currently modeled for this entity.':
      'Al momento non e modellato alcun grant ereditato per questa entita.',
    'Inheritance Chain': 'Catena di ereditarieta',
    'No resource hierarchy closure is currently materialized for this entity.':
      'Al momento non e materializzata alcuna chiusura della gerarchia risorse per questa entita.',
    'No group path is currently modeled for this entity.':
      'Al momento non e modellato alcun percorso di gruppo per questa entita.',
    'Effective Groups': 'Gruppi effettivi',
    Depth: 'Profondita',
    Parent: 'Padre',
    'No effective group closure is currently materialized for this entity.':
      'Al momento non e materializzata alcuna chiusura effettiva dei gruppi per questa entita.',
    'No role path is currently modeled for this entity.':
      'Al momento non e modellato alcun percorso di ruolo per questa entita.',
    'No risk finding is currently linked to this entity.':
      'Al momento nessun finding di rischio e collegato a questa entita.',
    'No recent change was recorded for the current environment.':
      'Nessuna modifica recente e stata registrata per l ambiente corrente.',
    '{value} is broadly exposed': '{value} e ampiamente esposto',
    '{principal} reaches {resource} with privileged rights':
      '{principal} raggiunge {resource} con diritti privilegiati',
    '{value} grants privileged access to a broad membership':
      '{value} concede accesso privilegiato a una membership ampia',
    '{principal} reaches {resource} through deep nesting':
      '{principal} raggiunge {resource} tramite nesting profondo',
    '{principals} privileged principals currently reach this resource.':
      '{principals} principali privilegiati raggiungono attualmente questa risorsa.',
    'This entitlement is currently materialized as privileged effective access in the index.':
      'Questa autorizzazione e attualmente materializzata nell indice come accesso effettivo privilegiato.',
    '{principals} direct members are currently covered by this privileged group path.':
      '{principals} membri diretti sono attualmente coperti da questo percorso di gruppo privilegiato.',
    'This access depends on multiple nested groups before the effective grant is applied.':
      'Questo accesso dipende da piu gruppi annidati prima che il grant effettivo venga applicato.',
    '{status} scan processed {resources} resources and {relationships} relationships across {targets} targets.':
      'La scansione {status} ha elaborato {resources} risorse e {relationships} relazioni su {targets} target.',
    'Real feature coverage': 'Copertura reale delle feature',
    'What the app really does today': "Cosa fa davvero l'app oggi",
    present: 'presente',
    partial: 'parziale',
    missing: 'mancante',
    'Required gaps': 'Gap obbligatori',
    'Capability inventory': 'Inventario capability',
    'Gap: {value}': 'Gap: {value}',
    'Feature inventory becomes available after the first authenticated refresh.':
      "L'inventario delle feature diventa disponibile dopo il primo refresh autenticato.",
    'Check your authenticator code to complete the sign-in.':
      'Controlla il codice del tuo autenticatore per completare l accesso.',
    'Initial setup completed. The workspace is now ready for your first scan.':
      'Setup iniziale completato. Il workspace e ora pronto per la prima scansione.',
    'Password updated. Sign in again to continue.':
      'Password aggiornata. Effettua di nuovo il login per continuare.',
    'MFA secret generated. Add it to your authenticator app, then confirm it with a TOTP code.':
      'Chiave MFA generata. Aggiungila alla tua app autenticatore, poi confermala con un codice TOTP.',
    'MFA enabled successfully for the local account.':
      'MFA attivata con successo per l account locale.',
    'Authentication provider created. You can now enable it for sign-in.':
      'Provider di autenticazione creato. Ora puoi abilitarlo per il login.',
    'Authentication provider disabled.': 'Provider di autenticazione disabilitato.',
    'Authentication provider enabled.': 'Provider di autenticazione abilitato.',
    'Authentication provider removed.': 'Provider di autenticazione rimosso.',
    'Target scan completed. The workspace has been refreshed with the latest data.':
      'Scansione del target completata. Il workspace e stato aggiornato con i dati piu recenti.',
    'Full scan completed. The workspace has been refreshed with the latest data.':
      'Scansione completa terminata. Il workspace e stato aggiornato con i dati piu recenti.',
    'Target disabled.': 'Target disabilitato.',
    'Target enabled.': 'Target abilitato.',
    'Target added. Run a scan when you are ready to collect live data.':
      'Target aggiunto. Avvia una scansione quando sei pronto a raccogliere dati live.',
    'Source bundle imported and merged into the workspace.':
      'Bundle sorgente importato e unito al workspace.',
    'Imported source disabled.': 'Sorgente importata disabilitata.',
    'Imported source enabled.': 'Sorgente importata abilitata.',
    'Imported source removed from the workspace.':
      'Sorgente importata rimossa dal workspace.',
    'Import file loaded into the editor. Review it before importing.':
      'File di import caricato nell editor. Verificalo prima di importarlo.',
    'Benchmark completed. Review the latest collection and query timings.':
      'Benchmark completato. Controlla gli ultimi tempi di raccolta e query.',
    'Pilot launchpad': 'Percorso guidato pilot',
    'Walk the shortest path from setup to first evidence':
      'Segui il percorso piu breve dal setup alla prima evidenza',
    'Use this guided flow to complete the minimum viable setup, collect the first live snapshot, validate explainability and produce evidence an operator can trust.':
      'Usa questo flusso guidato per completare il setup minimo, raccogliere il primo snapshot live, validare la spiegabilita e produrre evidenze affidabili per l operatore.',
    'Step-by-step rollout': 'Percorso passo dopo passo',
    'Open next guided step': 'Apri il prossimo passo guidato',
    'Freshness: {value}': 'Freschezza: {value}',
    'Last successful scan: {value}': 'Ultima scansione riuscita: {value}',
    'Raw batches: {value}': 'Batch raw: {value}',
    'Index rows: {value}': 'Righe indice: {value}',
    fresh: 'fresco',
    stale: 'obsoleto',
    empty: 'vuoto',
    'Use the recommended action below to keep the MVP rollout moving and generate your first trustworthy evidence.':
      'Usa l azione consigliata qui sotto per far avanzare il rollout MVP e generare la prima evidenza affidabile.',
    'Bootstrap administrator': 'Amministratore iniziale',
    'Authentication plane': 'Piano di autenticazione',
    'Local administrator MFA': 'MFA amministratore locale',
    'Target coverage': 'Copertura target',
    'Raw ingestion and normalization': 'Ingestione raw e normalizzazione',
    'Materialized access index': 'Indice materializzato degli accessi',
    'Connector readiness': 'Prontezza connettori',
    'Governance and evidence': 'Governance ed evidenze',
    'Proceed with the current administrator account.':
      'Procedi con l account amministratore corrente.',
    'Keep local admin as break-glass and review provider scopes periodically.':
      'Mantieni l admin locale come break-glass e rivedi periodicamente gli scope dei provider.',
    'Optionally configure LDAP or OAuth2/OIDC for delegated operator access.':
      'Configura facoltativamente LDAP o OAuth2/OIDC per l accesso delegato degli operatori.',
    'Keep a monitored break-glass account and review MFA recovery procedures.':
      'Mantieni un account break-glass monitorato e verifica le procedure di recupero MFA.',
    'Enable built-in TOTP MFA for local administrators, or rely on Keycloak/OIDC MFA for federated operators.':
      'Abilita la MFA TOTP integrata per gli amministratori locali oppure usa la MFA Keycloak/OIDC per gli operatori federati.',
    'Review target depth and connector coverage.':
      'Rivedi la profondita dei target e la copertura dei connettori.',
    'Add at least one monitored filesystem target or import an offline source bundle.':
      'Aggiungi almeno un target filesystem monitorato oppure importa un bundle sorgente offline.',
    'Monitor snapshot freshness and raw retention.':
      'Monitora la freschezza degli snapshot e la retention raw.',
    'Run a scan to populate raw ingestion and normalized entities.':
      'Esegui una scansione per popolare ingestione raw ed entita normalizzate.',
    'Use indexed access APIs for fast explain and exposure queries.':
      'Usa le API di accesso indicizzate per query rapide di explain ed esposizione.',
    'Complete a scan so the entitlement compiler can populate the access index.':
      'Completa una scansione in modo che il compilatore di entitlement possa popolare l indice di accesso.',
    'Keep connector credentials rotated and monitor failures.':
      'Mantieni ruotate le credenziali dei connettori e monitora i fallimenti.',
    'Configure official connector environments for the identity or cloud surfaces you need.':
      'Configura gli ambienti ufficiali dei connettori per le superfici identity o cloud di cui hai bisogno.',
    'Use review campaigns and remediation plans as the operational decision loop.':
      'Usa campagne di review e remediation plan come ciclo decisionale operativo.',
    'Create a first review campaign so the evidence and remediation workflow is exercised.':
      'Crea una prima campagna di review per esercitare il workflow di evidenze e remediation.',
    failed: 'fallito',
    success: 'riuscito',
    healthy: 'sano',
    running: 'in esecuzione',
  },
  de: {
    Language: 'Sprache',
    English: 'Englisch',
    Italian: 'Italienisch',
    German: 'Deutsch',
    French: 'Französisch',
    Spanish: 'Spanisch',
    Home: 'Start',
    Investigate: 'Analysieren',
    Govern: 'Governance',
    Sources: 'Quellen',
    Operations: 'Betrieb',
    Explain: 'Erklaeren',
    Exposure: 'Exponierung',
    'What-If': 'What-If',
    Reviews: 'Reviews',
    Remediation: 'Massnahmen',
    Auth: 'Authentifizierung',
    Collection: 'Erfassung',
    Imports: 'Importe',
    Identity: 'Identitaet',
    Status: 'Status',
    Platform: 'Plattform',
    Audit: 'Audit',
    Navigation: 'Navigation',
    'Section Menu': 'Bereichsmenue',
    'Open a module': 'Modul oeffnen',
    'Universal search': 'Universelle Suche',
    'Search users, groups, roles, folders, mailboxes, vaults...':
      'Suche nach Benutzern, Gruppen, Rollen, Ordnern, Postfaechern, Vaults...',
    'who • why • what if': 'wer • warum • was waere wenn',
    'Searching the graph...': 'Graph wird durchsucht...',
    'No matching identity or resource.': 'Keine passende Identitaet oder Ressource.',
    'Select a user or resource to update the live access views.':
      'Waehle einen Benutzer oder eine Ressource aus, um die Live-Zugriffsansichten zu aktualisieren.',
    'Command Center': 'Command Center',
    'Start from the shortest path to action': 'Beginne mit dem kuerzesten Weg zur Aktion',
    'Use this home to monitor the platform quickly, then jump into the specific workspace only when you need to investigate, govern, manage sources or review operations.':
      'Nutze diese Startseite fuer einen schnellen Plattformueberblick und springe erst dann in den passenden Workspace, wenn du analysieren, steuern, Quellen verwalten oder den Betrieb pruefen musst.',
    'Answer who has access and why': 'Beantworte, wer Zugriff hat und warum',
    'Run reviews and export evidence': 'Reviews ausfuehren und Nachweise exportieren',
    'Manage auth, targets and imports': 'Authentifizierung, Ziele und Importe verwalten',
    'Track scan health and platform posture': 'Scan-Zustand und Plattformstatus verfolgen',
    'Question Studio': 'Question Studio',
    'Why does this access exist?': 'Warum existiert dieser Zugriff?',
    Principal: 'Prinzipal',
    Resource: 'Ressource',
    Permissions: 'Berechtigungen',
    Paths: 'Pfade',
    Risk: 'Risiko',
    'No graph to render for this access path.':
      'Fuer diesen Zugriffspfad kann kein Graph dargestellt werden.',
    'Access Map': 'Zugriffskarte',
    'Clean path view for the selected entitlement':
      'Saubere Pfadansicht fuer die ausgewaehlte Berechtigung',
    'Each lane shows the effective route from identity to resource, with one transition per step.':
      'Jede Spur zeigt den effektiven Weg von der Identitaet zur Ressource mit genau einem Uebergang pro Schritt.',
    Nodes: 'Knoten',
    Links: 'Verbindungen',
    Pipeline: 'Pipeline',
    'Index refresh': 'Index-Aktualisierung',
    'Path {index}': 'Pfad {index}',
    'risk {value}': 'Risiko {value}',
    'Showing the top {visible} paths out of {total} to keep the view readable.':
      'Es werden die ersten {visible} von {total} Pfaden angezeigt, damit die Ansicht lesbar bleibt.',
    Mode: 'Modus',
    'Reused rows': 'Wiederverwendete Zeilen',
    'Recomputed rows': 'Neu berechnete Zeilen',
    'Impacted principals': 'Betroffene Prinzipale',
    'Impacted resources': 'Betroffene Ressourcen',
    'Group closure refresh': 'Aktualisierung der Gruppenschliessung',
    'Hierarchy refresh': 'Aktualisierung der Hierarchie',
    'Carry-forward': 'Uebernommen',
    Existing: 'Vorhanden',
    Delta: 'Delta',
    'Full rebuild': 'Vollstaendiger Neuaufbau',
    'Previous snapshot: {value}': 'Vorheriger Snapshot: {value}',
    'The next successful scan will publish an index refresh summary.':
      'Der naechste erfolgreiche Scan veroeffentlicht eine Zusammenfassung der Index-Aktualisierung.',
    'Access index refresh uses carry-forward when the graph is unchanged and delta recomputation when the impacted scope stays small.':
      'Die Aktualisierung des Zugriffsindex uebernimmt Daten bei unveraendertem Graphen und nutzt Delta-Neuberechnung, wenn der betroffene Umfang klein bleibt.',
    Rows: 'Zeilen',
    Previous: 'Zurueck',
    Next: 'Weiter',
    'No effective principals for this resource.':
      'Keine effektiven Prinzipale fuer diese Ressource.',
    '{count} effective principals': '{count} effektive Prinzipale',
    'Showing {start}-{end}': 'Zeige {start}-{end}',
    'Focused Entity': 'Fokussierte Entitaet',
    'Why this matters': 'Warum das wichtig ist',
    'Selected resource': 'Ausgewaehlte Ressource',
    principals: 'Prinzipale',
    'Monitored Targets': 'Ueberwachte Ziele',
    'Filesystem scope': 'Dateisystem-Bereich',
    'Target name': 'Zielname',
    'Filesystem path': 'Dateisystempfad',
    Connection: 'Verbindung',
    'Local / mounted': 'Lokal / eingebunden',
    'Remote Linux via SSH': 'Entferntes Linux ueber SSH',
    'Latest Scan': 'Letzter Scan',
    'Operational status': 'Betriebsstatus',
    Finished: 'Abgeschlossen',
    Duration: 'Dauer',
    Warnings: 'Warnungen',
    Governance: 'Governance',
    'Access reviews': 'Zugriffspruefungen',
    Scope: 'Umfang',
    Action: 'Aktion',
    Progress: 'Fortschritt',
    'Workspace sections': 'Workspace-Bereiche',
    Workspace: 'Arbeitsbereich',
    'Workspace: {value}': 'Arbeitsbereich: {value}',
    'Organizations and environments': 'Organisationen und Umgebungen',
    'Use dedicated workspaces to isolate a customer, business unit or environment while keeping authentication and platform administration in one control plane.':
      'Verwende dedizierte Workspaces, um einen Kunden, eine Business Unit oder eine Umgebung zu isolieren und gleichzeitig Authentifizierung und Plattformverwaltung in einer gemeinsamen Steuerungsebene zu behalten.',
    'Update active workspace': 'Aktiven Workspace aktualisieren',
    'Workspace name': 'Workspace-Name',
    'Save workspace details': 'Workspace-Details speichern',
    'Create workspace': 'Workspace erstellen',
    'Workspace activated. The control plane has been refreshed.':
      'Workspace aktiviert. Die Steuerungsebene wurde aktualisiert.',
    'Workspace created. Switch to it when you are ready to isolate another organization or environment.':
      'Workspace erstellt. Wechsle dorthin, wenn du eine weitere Organisation oder Umgebung isolieren willst.',
    'Workspace details updated.': 'Workspace-Details aktualisiert.',
    'Unable to activate the workspace.': 'Workspace konnte nicht aktiviert werden.',
    'Unable to create the workspace.': 'Workspace konnte nicht erstellt werden.',
    'Unable to update the workspace.': 'Workspace konnte nicht aktualisiert werden.',
    Slug: 'Slug',
    'On-prem': 'On-Prem',
    Hybrid: 'Hybrid',
    Cloud: 'Cloud',
    'Investigation graph': 'Untersuchungsgraf',
    'Dense neighborhood view for the focused entity':
      'Dichte Nachbarschaftsansicht fuer die fokussierte Entitaet',
    'Use the dense graph to inspect nearby grants, memberships and inherited routes without collapsing everything into a single path.':
      'Nutze den dichten Graphen, um nahe Grants, Mitgliedschaften und vererbte Routen zu untersuchen, ohne alles auf einen einzelnen Pfad zu reduzieren.',
    'No investigation graph is available for this focus yet.':
      'Fuer diesen Fokus ist noch kein Untersuchungsgraf verfuegbar.',
    'Open investigation graph': 'Untersuchungsgraf oeffnen',
    'Hide investigation graph': 'Untersuchungsgraf ausblenden',
    Density: 'Dichte',
    Compact: 'Kompakt',
    Expanded: 'Erweitert',
    'Loading current page...': 'Aktuelle Seite wird geladen...',
    'Loading access window...': 'Zugriffsfenster wird geladen...',
    'This investigation graph is currently capped to {nodes} nodes and {edges} links so the view stays responsive.':
      'Dieser Untersuchungsgraf ist auf {nodes} Knoten und {edges} Verbindungen begrenzt, damit die Ansicht reaktionsschnell bleibt.',
    'Start from a short operational dashboard with top exposure, quick actions and recent platform signals before drilling into a workflow.':
      'Starte mit einem kompakten operativen Dashboard mit Top-Exposition, Schnellaktionen und aktuellen Plattformsignalen, bevor du in einen Workflow einsteigst.',
    'Use the explain, exposure and what-if views to answer who has access, why it exists and what changes would do.':
      'Nutze Explain-, Exposure- und What-if-Ansichten, um zu verstehen, wer Zugriff hat, warum er besteht und was eine Aenderung bewirken wuerde.',
    'Keep decisions, revoke plans and review evidence together so the governance loop stays clear and deterministic.':
      'Halte Entscheidungen, Entzugsplaene und Review-Nachweise zusammen, damit der Governance-Kreis klar und deterministisch bleibt.',
    'Configure administrators, sign-in providers, monitored targets, offline bundles and cross-source identity linking in one place.':
      'Konfiguriere Administratoren, Anmeldeanbieter, ueberwachte Ziele, Offline-Bundles und quellenuebergreifende Identitaetsverknuepfung an einem Ort.',
    'Monitor scan health, runtime posture, connector readiness, benchmarks and administrator activity without cluttering the investigation flow.':
      'Ueberwache Scan-Zustand, Runtime-Posture, Connector-Bereitschaft, Benchmarks und Administratoraktivitaet, ohne den Untersuchungsfluss zu ueberladen.',
    'Offline Sources': 'Offline-Quellen',
    'Import local JSON bundles': 'Lokale JSON-Bundles importieren',
    'Identity Fabric': 'Identity Fabric',
    'Cross-source linked identities': 'Quellenuebergreifend verknuepfte Identitaeten',
    'Combined access footprint': 'Kombinierter Zugriffs-Footprint',
    '{count} linked identities | {permissions}': '{count} verknuepfte Identitaeten | {permissions}',
    'Connect at least two identity sources for the same organization to unlock cross-source correlation and a unified user footprint.':
      'Verbinde mindestens zwei Identitaetsquellen derselben Organisation, um quellenuebergreifende Korrelation und einen einheitlichen Benutzer-Footprint freizuschalten.',
    'confidence {value}': 'Konfidenz {value}',
    Performance: 'Leistung',
    'Real local benchmark': 'Realer lokaler Benchmark',
    'Running...': 'Laeuft...',
    Targets: 'Ziele',
    'Run the live benchmark on demand so normal workspace loading stays fast.':
      'Fuehre den Live-Benchmark bei Bedarf aus, damit das normale Laden des Workspace schnell bleibt.',
    'Official Blueprint': 'Offizieller Blueprint',
    'Cloud and IAM integration notes': 'Cloud- und IAM-Integrationshinweise',
    Runtime: 'Runtime',
    Limitation: 'Einschraenkung',
    'Official documentation': 'Offizielle Dokumentation',
    'Audit Trail': 'Audit-Trail',
    'Recent administrator actions': 'Letzte Administratoraktionen',
    'No audit event has been recorded yet.': 'Es wurde noch kein Audit-Ereignis aufgezeichnet.',
    'Platform posture becomes available after administrator authentication.':
      'Die Plattform-Posture wird nach der Administratoranmeldung verfuegbar.',
    '{kind} discovered from {source} in the {environment} estate.':
      '{kind} aus {source} in der {environment}-Umgebung erkannt.',
    '{count} inbound relationships reference this entity.':
      '{count} eingehende Beziehungen verweisen auf diese Entitaet.',
    '{count} outbound relationships originate from this entity.':
      '{count} ausgehende Beziehungen gehen von dieser Entitaet aus.',
    'Observed tags: {value}.': 'Beobachtete Tags: {value}.',
    'No extra classification tags were attached.': 'Es wurden keine zusaetzlichen Klassifizierungs-Tags angehaengt.',
    'Current score: {value}.': 'Aktueller Wert: {value}.',
    'Current classification signals: {value}.': 'Aktuelle Klassifizierungssignale: {value}.',
    'Current classification is based on the entity profile only.':
      'Die aktuelle Klassifizierung basiert nur auf dem Entitaetsprofil.',
    'Owner context: {value}.': 'Owner-Kontext: {value}.',
    'No explicit owner was recorded for this entity.':
      'Fuer diese Entitaet wurde kein expliziter Owner erfasst.',
    'Current risk score: {value}.': 'Aktueller Risikowert: {value}.',
    '{inbound} inbound and {outbound} outbound relationships contribute to the current exposure graph.':
      '{inbound} eingehende und {outbound} ausgehende Beziehungen tragen zum aktuellen Expositionsgraphen bei.',
    'Important context: {value}.': 'Wichtiger Kontext: {value}.',
    'No special tags amplified the risk context for this entity.':
      'Keine speziellen Tags haben den Risikokontext fuer diese Entitaet verstaerkt.',
    'avg {average} ms | p95 {p95} ms': 'Durchschnitt {average} ms | p95 {p95} ms',
    '{count} runs': '{count} Durchlaeufe',
    'Enterprise posture': 'Enterprise-Posture',
    Storage: 'Storage',
    Search: 'Suche',
    Cache: 'Cache',
    Analytics: 'Analytik',
    connected: 'verbunden',
    'not connected': 'nicht verbunden',
    'Operational details': 'Betriebsdetails',
    'Operational Flow': 'Betriebsfluss',
    'Readiness and next actions': 'Bereitschaft und naechste Aktionen',
    'Overall status': 'Gesamtstatus',
    Completion: 'Abschluss',
    'Open actions': 'Offene Aktionen',
    Ready: 'Bereit',
    'Recommended next actions': 'Empfohlene naechste Aktionen',
    'Operational readiness is calculated after authentication.':
      'Die operative Bereitschaft wird nach der Authentifizierung berechnet.',
    Connectors: 'Konnektoren',
    'Official integration posture': 'Offizielle Integrations-Posture',
    '{count} entities': '{count} Entitaeten',
    '{count} links': '{count} Verknuepfungen',
    'Supported entities': 'Unterstuetzte Entitaeten',
    'Required environment': 'Erforderliche Umgebung',
    'Required permissions': 'Erforderliche Berechtigungen',
    'Linked identities': 'Verknuepfte Identitaeten',
    'Load JSON file': 'JSON-Datei laden',
    'Bundle JSON': 'JSON-Bundle',
    'Importing...': 'Importiere...',
    'Import local source': 'Lokale Quelle importieren',
    'Focus on access questions': 'Fokus auf Zugriffsfragen',
    'Manage identities and collection': 'Identitaeten und Erfassung verwalten',
    'Track readiness and performance': 'Bereitschaft und Leistung verfolgen',
    'What still needs attention': 'Was noch Aufmerksamkeit braucht',
    'MVP Readiness': 'MVP-Bereitschaft',
    complete: 'abgeschlossen',
    ready: 'bereit',
    'Selected Step': 'Ausgewaehlter Schritt',
    required: 'erforderlich',
    recommended: 'empfohlen',
    'Recommended action: {value}': 'Empfohlene Aktion: {value}',
    'Data freshness: {value}': 'Datenaktualitaet: {value}',
    'Open relevant section': 'Relevanten Bereich oeffnen',
    'Blockers: {value}': 'Blocker: {value}',
    Active: 'Aktiv',
    Configured: 'Konfiguriert',
    Attention: 'Achtung',
    Disabled: 'Deaktiviert',
    Optional: 'Optional',
    Healthy: 'Gesund',
    Critical: 'Kritisch',
    Info: 'Info',
    'Live collector': 'Live-Collector',
    'Partial runtime': 'Teilweise Runtime',
    'Blueprint only': 'Nur Blueprint',
    Auto: 'Auto',
    'SSH remote': 'SSH remote',
    'Local path': 'Lokaler Pfad',
    Pending: 'Ausstehend',
    disabled: 'deaktiviert',
    enabled: 'aktiviert',
    'n/d': 'k. A.',
    completed: 'abgeschlossen',
    warning: 'Warnung',
    idle: 'Leerlauf',
    Freshness: 'Aktualitaet',
    'privileged principals': 'privilegierte Prinzipale',
    'delegated paths': 'delegierte Pfade',
    'Most exposed resources': 'Am staerksten exponierte Ressourcen',
    'No exposure hotspot is available yet.':
      'Noch ist kein Expositions-Hotspot verfuegbar.',
    'Risk Dashboard': 'Risikodashboard',
    'Top risk findings': 'Top-Risikofindings',
    'No risk finding is available yet.':
      'Noch ist kein Risikofinding verfuegbar.',
    'Hidden Admin Rights': 'Versteckte Admin-Rechte',
    'Indirect privileged paths': 'Indirekte privilegierte Pfade',
    Findings: 'Findings',
    'Suggested cleanups': 'Empfohlene Bereinigungen',
    'No hidden admin right is currently flagged.':
      'Aktuell ist kein verstecktes Admin-Recht markiert.',
    'Recently Changed Access': 'Zuletzt geaenderter Zugriff',
    'Latest processing events': 'Neueste Verarbeitungsvorgaenge',
    'No recent platform change is available yet.':
      'Aktuell ist keine aktuelle Plattformaenderung verfuegbar.',
    'Access Overview': 'Zugriffsueberblick',
    'Grants and paths': 'Grants und Pfade',
    'Risk Findings': 'Risikofindings',
    'Change History': 'Aenderungshistorie',
    'User view': 'Benutzersicht',
    'Resource view': 'Ressourcensicht',
    'Direct Grants': 'Direkte Grants',
    'Inherited Grants': 'Geerbte Grants',
    'Group Paths': 'Gruppenpfade',
    'Role Paths': 'Rollenpfade',
    'Admin Rights': 'Admin-Rechte',
    Kind: 'Art',
    Criticality: 'Kritikalitaet',
    'No entity selected': 'Keine Entitaet ausgewaehlt',
    'No direct grant is currently modeled for this entity.':
      'Fuer diese Entitaet ist aktuell kein direkter Grant modelliert.',
    'No inherited grant is currently modeled for this entity.':
      'Fuer diese Entitaet ist aktuell kein geerbter Grant modelliert.',
    'Inheritance Chain': 'Vererbungskette',
    'No resource hierarchy closure is currently materialized for this entity.':
      'Aktuell ist keine Ressourcenhierarchie-Abschlussmenge fuer diese Entitaet materialisiert.',
    'No group path is currently modeled for this entity.':
      'Fuer diese Entitaet ist aktuell kein Gruppenpfad modelliert.',
    'Effective Groups': 'Effektive Gruppen',
    Depth: 'Tiefe',
    Parent: 'Elternknoten',
    'No effective group closure is currently materialized for this entity.':
      'Aktuell ist keine effektive Gruppenabschlussmenge fuer diese Entitaet materialisiert.',
    'No role path is currently modeled for this entity.':
      'Fuer diese Entitaet ist aktuell kein Rollenpfad modelliert.',
    'No risk finding is currently linked to this entity.':
      'Aktuell ist kein Risikofinding mit dieser Entitaet verknuepft.',
    'No recent change was recorded for the current environment.':
      'Fuer die aktuelle Umgebung wurde keine recente Aenderung erfasst.',
    'Why this entity matters': 'Warum diese Entitaet wichtig ist',
    'How criticality is interpreted': 'Wie Kritikalitaet interpretiert wird',
    'Criticality is the business importance score assigned by the normalization pipeline. Higher values usually indicate entities tied to sensitive resources, privileged routes or important operational scope.':
      'Kritikalitaet ist der Geschaeftswichtigkeitswert der Normalisierungspipeline. Hoehere Werte deuten meist auf Entitaeten mit sensiblen Ressourcen, privilegierten Pfaden oder wichtigem Betriebsumfang hin.',
    'Why the risk score is elevated': 'Warum der Risikowert erhoeht ist',
    'Risk is derived from effective permissions, privilege indicators, indirect grant paths and breadth of exposure. It is meant to explain urgency, not hide it behind a black-box score.':
      'Das Risiko leitet sich aus effektiven Berechtigungen, Privilegindikatoren, indirekten Grant-Pfaden und der Breite der Exposition ab. Es soll Dringlichkeit erklaeren, nicht hinter einem Black-Box-Wert verstecken.',
    'Select any entity to inspect its neighborhood.':
      'Waehle eine beliebige Entitaet, um ihre Umgebung zu untersuchen.',
    '{value} is broadly exposed': '{value} ist breit exponiert',
    '{principal} reaches {resource} with privileged rights':
      '{principal} erreicht {resource} mit privilegierten Rechten',
    '{value} grants privileged access to a broad membership':
      '{value} gewaehrt privilegierten Zugriff an eine breite Mitgliedschaft',
    '{principal} reaches {resource} through deep nesting':
      '{principal} erreicht {resource} durch tiefe Verschachtelung',
    '{principals} privileged principals currently reach this resource.':
      '{principals} privilegierte Prinzipale erreichen diese Ressource aktuell.',
    'This entitlement is currently materialized as privileged effective access in the index.':
      'Diese Berechtigung ist aktuell als privilegierter effektiver Zugriff im Index materialisiert.',
    '{principals} direct members are currently covered by this privileged group path.':
      '{principals} direkte Mitglieder werden aktuell ueber diesen privilegierten Gruppenpfad abgedeckt.',
    'This access depends on multiple nested groups before the effective grant is applied.':
      'Dieser Zugriff haengt von mehreren verschachtelten Gruppen ab, bevor der effektive Grant angewendet wird.',
    '{status} scan processed {resources} resources and {relationships} relationships across {targets} targets.':
      'Der Scan mit Status {status} hat {resources} Ressourcen und {relationships} Beziehungen ueber {targets} Ziele verarbeitet.',
    'Real feature coverage': 'Reale Feature-Abdeckung',
    'What the app really does today': 'Was die App heute wirklich kann',
    present: 'vorhanden',
    partial: 'teilweise',
    missing: 'fehlend',
    'Required gaps': 'Erforderliche Luecken',
    'Capability inventory': 'Faehigkeiten-Inventar',
    'Gap: {value}': 'Luecke: {value}',
    'Feature inventory becomes available after the first authenticated refresh.':
      'Das Feature-Inventar wird nach der ersten authentifizierten Aktualisierung verfuegbar.',
    'Check your authenticator code to complete the sign-in.':
      'Pruefe den Code deiner Authenticator-App, um die Anmeldung abzuschliessen.',
    'Initial setup completed. The workspace is now ready for your first scan.':
      'Die Ersteinrichtung ist abgeschlossen. Der Workspace ist jetzt fuer den ersten Scan bereit.',
    'Password updated. Sign in again to continue.':
      'Passwort aktualisiert. Melde dich erneut an, um fortzufahren.',
    'MFA secret generated. Add it to your authenticator app, then confirm it with a TOTP code.':
      'MFA-Geheimnis erzeugt. Fuege es deiner Authenticator-App hinzu und bestaetige es dann mit einem TOTP-Code.',
    'MFA enabled successfully for the local account.':
      'MFA wurde fuer das lokale Konto erfolgreich aktiviert.',
    'Authentication provider created. You can now enable it for sign-in.':
      'Authentifizierungsanbieter erstellt. Du kannst ihn jetzt fuer die Anmeldung aktivieren.',
    'Authentication provider disabled.': 'Authentifizierungsanbieter deaktiviert.',
    'Authentication provider enabled.': 'Authentifizierungsanbieter aktiviert.',
    'Authentication provider removed.': 'Authentifizierungsanbieter entfernt.',
    'Target scan completed. The workspace has been refreshed with the latest data.':
      'Der Ziel-Scan wurde abgeschlossen. Der Workspace wurde mit den neuesten Daten aktualisiert.',
    'Full scan completed. The workspace has been refreshed with the latest data.':
      'Der Vollscan wurde abgeschlossen. Der Workspace wurde mit den neuesten Daten aktualisiert.',
    'Target disabled.': 'Ziel deaktiviert.',
    'Target enabled.': 'Ziel aktiviert.',
    'Target added. Run a scan when you are ready to collect live data.':
      'Ziel hinzugefuegt. Starte einen Scan, wenn du Live-Daten erfassen moechtest.',
    'Source bundle imported and merged into the workspace.':
      'Quell-Bundle importiert und mit dem Workspace zusammengefuehrt.',
    'Imported source disabled.': 'Importierte Quelle deaktiviert.',
    'Imported source enabled.': 'Importierte Quelle aktiviert.',
    'Imported source removed from the workspace.':
      'Importierte Quelle aus dem Workspace entfernt.',
    'Import file loaded into the editor. Review it before importing.':
      'Importdatei in den Editor geladen. Pruefe sie vor dem Import.',
    'Benchmark completed. Review the latest collection and query timings.':
      'Benchmark abgeschlossen. Pruefe die letzten Erfassungs- und Abfragezeiten.',
    'Pilot launchpad': 'Pilot-Startpfad',
    'Walk the shortest path from setup to first evidence':
      'Gehe den kuerzesten Weg vom Setup bis zum ersten Nachweis',
    'Use this guided flow to complete the minimum viable setup, collect the first live snapshot, validate explainability and produce evidence an operator can trust.':
      'Nutze diesen gefuehrten Ablauf, um das minimale Setup abzuschliessen, den ersten Live-Snapshot zu erfassen, die Erklaerbarkeit zu pruefen und Nachweise zu erzeugen, denen Operatoren vertrauen koennen.',
    'Step-by-step rollout': 'Schrittweise Einfuehrung',
    'Open next guided step': 'Naechsten gefuehrten Schritt oeffnen',
    'Freshness: {value}': 'Frische: {value}',
    'Last successful scan: {value}': 'Letzter erfolgreicher Scan: {value}',
    'Raw batches: {value}': 'Raw-Batches: {value}',
    'Index rows: {value}': 'Indexzeilen: {value}',
    fresh: 'frisch',
    stale: 'veraltet',
    empty: 'leer',
    'Use the recommended action below to keep the MVP rollout moving and generate your first trustworthy evidence.':
      'Nutze die empfohlene Aktion unten, um den MVP-Rollout voranzubringen und den ersten verlaesslichen Nachweis zu erzeugen.',
    'Bootstrap administrator': 'Bootstrap-Administrator',
    'Authentication plane': 'Authentifizierungsebene',
    'Local administrator MFA': 'Lokale Administrator-MFA',
    'Target coverage': 'Zielabdeckung',
    'Raw ingestion and normalization': 'Rohaufnahme und Normalisierung',
    'Materialized access index': 'Materialisierter Zugriffsindex',
    'Connector readiness': 'Connector-Bereitschaft',
    'Governance and evidence': 'Governance und Nachweise',
    'Proceed with the current administrator account.':
      'Fahre mit dem aktuellen Administratorkonto fort.',
    'Keep local admin as break-glass and review provider scopes periodically.':
      'Behalte den lokalen Admin als Break-Glass-Konto und pruefe die Provider-Scopes regelmaessig.',
    'Optionally configure LDAP or OAuth2/OIDC for delegated operator access.':
      'Konfiguriere optional LDAP oder OAuth2/OIDC fuer delegierten Operatorzugriff.',
    'Keep a monitored break-glass account and review MFA recovery procedures.':
      'Halte ein ueberwachtes Break-Glass-Konto bereit und pruefe die MFA-Wiederherstellungsverfahren.',
    'Enable built-in TOTP MFA for local administrators, or rely on Keycloak/OIDC MFA for federated operators.':
      'Aktiviere integrierte TOTP-MFA fuer lokale Administratoren oder nutze Keycloak/OIDC-MFA fuer föderierte Operatoren.',
    'Review target depth and connector coverage.':
      'Pruefe Zieltiefe und Connector-Abdeckung.',
    'Add at least one monitored filesystem target or import an offline source bundle.':
      'Fuege mindestens ein ueberwachtes Dateisystemziel hinzu oder importiere ein Offline-Quell-Bundle.',
    'Monitor snapshot freshness and raw retention.':
      'Ueberwache Snapshot-Aktualitaet und Raw-Retention.',
    'Run a scan to populate raw ingestion and normalized entities.':
      'Fuehre einen Scan aus, um Rohaufnahme und normalisierte Entitaeten zu fuellen.',
    'Use indexed access APIs for fast explain and exposure queries.':
      'Nutze indizierte Zugriffs-APIs fuer schnelle Explain- und Exponierungsabfragen.',
    'Complete a scan so the entitlement compiler can populate the access index.':
      'Schliesse einen Scan ab, damit der Entitlement-Compiler den Zugriffsindex fuellen kann.',
    'Keep connector credentials rotated and monitor failures.':
      'Halte Connector-Anmeldedaten rotiert und ueberwache Fehler.',
    'Configure official connector environments for the identity or cloud surfaces you need.':
      'Konfiguriere offizielle Connector-Umgebungen fuer die benoetigten Identity- oder Cloud-Flaechen.',
    'Use review campaigns and remediation plans as the operational decision loop.':
      'Nutze Review-Kampagnen und Remediation-Plaene als operativen Entscheidungszyklus.',
    'Create a first review campaign so the evidence and remediation workflow is exercised.':
      'Erstelle eine erste Review-Kampagne, damit der Nachweis- und Remediation-Workflow geuebt wird.',
    failed: 'fehlgeschlagen',
    success: 'erfolgreich',
    healthy: 'gesund',
    running: 'laeuft',
  },
  fr: {
    Language: 'Langue',
    English: 'Anglais',
    Italian: 'Italien',
    German: 'Allemand',
    French: 'Français',
    Spanish: 'Espagnol',
    Home: 'Accueil',
    Investigate: 'Analyser',
    Govern: 'Gouvernance',
    Sources: 'Sources',
    Operations: 'Operations',
    Explain: 'Expliquer',
    Exposure: 'Exposition',
    'What-If': 'What-If',
    Reviews: 'Revues',
    Remediation: 'Remediation',
    Auth: 'Authentification',
    Collection: 'Collecte',
    Imports: 'Imports',
    Identity: 'Identite',
    Status: 'Statut',
    Platform: 'Plateforme',
    Audit: 'Audit',
    Navigation: 'Navigation',
    'Section Menu': 'Menu de section',
    'Open a module': 'Ouvrir un module',
    'Universal search': 'Recherche universelle',
    'Search users, groups, roles, folders, mailboxes, vaults...':
      'Rechercher des utilisateurs, groupes, roles, dossiers, boites mail, coffres...',
    'Searching the graph...': 'Recherche dans le graphe...',
    'No matching identity or resource.': 'Aucune identite ou ressource correspondante.',
    'Select a user or resource to update the live access views.':
      "Selectionnez un utilisateur ou une ressource pour mettre a jour les vues d'acces en direct.",
    'Question Studio': 'Studio de question',
    'Why does this access exist?': 'Pourquoi cet acces existe-t-il ?',
    Principal: 'Principal',
    Resource: 'Ressource',
    Permissions: 'Permissions',
    Paths: 'Chemins',
    Risk: 'Risque',
    'Access Map': "Carte d'acces",
    'Clean path view for the selected entitlement':
      'Vue de chemin claire pour le droit selectionne',
    'Each lane shows the effective route from identity to resource, with one transition per step.':
      "Chaque couloir montre le chemin effectif de l'identite a la ressource, avec une transition par etape.",
    Nodes: 'Noeuds',
    Links: 'Liens',
    Pipeline: 'Pipeline',
    'Index refresh': "Rafraichissement de l'index",
    Mode: 'Mode',
    'Reused rows': 'Lignes reutilisees',
    'Recomputed rows': 'Lignes recalculees',
    'Impacted principals': 'Principaux touches',
    'Impacted resources': 'Ressources touchees',
    'Group closure refresh': 'Rafraichissement de la fermeture des groupes',
    'Hierarchy refresh': 'Rafraichissement de la hierarchie',
    'Carry-forward': 'Reprise',
    Existing: 'Existant',
    Delta: 'Delta',
    'Full rebuild': 'Reconstruction complete',
    'Previous snapshot: {value}': 'Snapshot precedent : {value}',
    'The next successful scan will publish an index refresh summary.':
      "Le prochain scan reussi publiera un resume du rafraichissement de l'index.",
    'Access index refresh uses carry-forward when the graph is unchanged and delta recomputation when the impacted scope stays small.':
      "Le rafraichissement de l'index d'acces reprend l'etat precedent quand le graphe ne change pas et utilise un recalcul delta lorsque la zone impactee reste reduite.",
    Rows: 'Lignes',
    Previous: 'Precedent',
    Next: 'Suivant',
    'Focused Entity': 'Entite cible',
    'Why this matters': 'Pourquoi c est important',
    'Selected resource': 'Ressource selectionnee',
    principals: 'principaux',
    'Monitored Targets': 'Cibles surveillees',
    'Filesystem scope': 'Perimetre filesysteme',
    'Target name': 'Nom de la cible',
    'Filesystem path': 'Chemin filesysteme',
    Connection: 'Connexion',
    'Local / mounted': 'Local / monte',
    'Remote Linux via SSH': 'Linux distant via SSH',
    'Latest Scan': 'Dernier scan',
    'Operational status': 'Etat operationnel',
    Finished: 'Termine',
    Duration: 'Duree',
    Warnings: 'Avertissements',
    Governance: 'Gouvernance',
    'Access reviews': 'Revues d acces',
    Scope: 'Portee',
    Action: 'Action',
    Progress: 'Progression',
    'Workspace sections': 'Sections du workspace',
    Workspace: 'Espace de travail',
    'Workspace: {value}': 'Espace de travail : {value}',
    'Organizations and environments': 'Organisations et environnements',
    'Use dedicated workspaces to isolate a customer, business unit or environment while keeping authentication and platform administration in one control plane.':
      'Utilisez des espaces de travail dedies pour isoler un client, une unite metier ou un environnement tout en gardant l authentification et l administration de la plateforme dans un seul plan de controle.',
    'Update active workspace': 'Mettre a jour l espace actif',
    'Workspace name': 'Nom de l espace',
    'Save workspace details': 'Enregistrer les details de l espace',
    'Create workspace': 'Creer un espace',
    'Workspace activated. The control plane has been refreshed.':
      'Espace active. Le plan de controle a ete actualise.',
    'Workspace created. Switch to it when you are ready to isolate another organization or environment.':
      'Espace cree. Basculez dessus quand vous etes pret a isoler une autre organisation ou un autre environnement.',
    'Workspace details updated.': 'Details de l espace mis a jour.',
    'Unable to activate the workspace.': 'Impossible d activer l espace.',
    'Unable to create the workspace.': 'Impossible de creer l espace.',
    'Unable to update the workspace.': 'Impossible de mettre a jour l espace.',
    Slug: 'Slug',
    'On-prem': 'Sur site',
    Hybrid: 'Hybride',
    Cloud: 'Cloud',
    'Investigation graph': 'Graphe d investigation',
    'Dense neighborhood view for the focused entity':
      'Vue dense du voisinage pour l entite cible',
    'Use the dense graph to inspect nearby grants, memberships and inherited routes without collapsing everything into a single path.':
      'Utilisez le graphe dense pour examiner les grants proches, les appartenances et les chemins herites sans tout reduire a un seul chemin.',
    'No investigation graph is available for this focus yet.':
      'Aucun graphe d investigation n est encore disponible pour ce focus.',
    'Open investigation graph': 'Ouvrir le graphe d investigation',
    'Hide investigation graph': 'Masquer le graphe d investigation',
    Density: 'Densite',
    Compact: 'Compact',
    Expanded: 'Etendu',
    'Loading current page...': 'Chargement de la page en cours...',
    'Loading access window...': 'Chargement de la fenetre d acces...',
    'This investigation graph is currently capped to {nodes} nodes and {edges} links so the view stays responsive.':
      'Ce graphe d investigation est limite a {nodes} noeuds et {edges} liens pour garder une vue reactive.',
    'Start from a short operational dashboard with top exposure, quick actions and recent platform signals before drilling into a workflow.':
      "Commencez par un tableau de bord operationnel compact avec l exposition principale, des actions rapides et les signaux recents avant d entrer dans un workflow.",
    'Use the explain, exposure and what-if views to answer who has access, why it exists and what changes would do.':
      "Utilisez les vues explain, exposure et what-if pour repondre a qui a acces, pourquoi il existe et ce que changerait une modification.",
    'Keep decisions, revoke plans and review evidence together so the governance loop stays clear and deterministic.':
      "Gardez ensemble les decisions, les plans de revocation et les preuves de revue afin que la boucle de gouvernance reste claire et deterministe.",
    'Configure administrators, sign-in providers, monitored targets, offline bundles and cross-source identity linking in one place.':
      "Configurez administrateurs, fournisseurs de connexion, cibles surveillees, bundles hors ligne et liaison d identites inter-sources au meme endroit.",
    'Monitor scan health, runtime posture, connector readiness, benchmarks and administrator activity without cluttering the investigation flow.':
      "Surveillez la sante des scans, la posture runtime, l etat des connecteurs, les benchmarks et l activite administrateur sans encombrer le flux d investigation.",
    'Offline Sources': 'Sources hors ligne',
    'Import local JSON bundles': 'Importer des bundles JSON locaux',
    'Identity Fabric': 'Identity Fabric',
    'Cross-source linked identities': 'Identites liees entre sources',
    'Combined access footprint': "Empreinte d acces combinee",
    '{count} linked identities | {permissions}': '{count} identites liees | {permissions}',
    'Connect at least two identity sources for the same organization to unlock cross-source correlation and a unified user footprint.':
      "Connectez au moins deux sources d identite pour la meme organisation afin d activer la correlation inter-sources et une empreinte utilisateur unifiee.",
    'confidence {value}': 'confiance {value}',
    Performance: 'Performance',
    'Real local benchmark': 'Benchmark local reel',
    'Running...': 'Execution...',
    Targets: 'Cibles',
    'Run the live benchmark on demand so normal workspace loading stays fast.':
      "Lancez le benchmark live a la demande afin que le chargement normal du workspace reste rapide.",
    'Official Blueprint': 'Blueprint officiel',
    'Cloud and IAM integration notes': 'Notes d integration cloud et IAM',
    Runtime: 'Runtime',
    Limitation: 'Limitation',
    'Official documentation': 'Documentation officielle',
    'Audit Trail': "Piste d audit",
    'Recent administrator actions': 'Actions administrateur recentes',
    'No audit event has been recorded yet.': "Aucun evenement d audit n a encore ete enregistre.",
    'Platform posture becomes available after administrator authentication.':
      "La posture de la plateforme devient disponible apres l authentification de l administrateur.",
    '{kind} discovered from {source} in the {environment} estate.':
      '{kind} decouvert depuis {source} dans l environnement {environment}.',
    '{count} inbound relationships reference this entity.':
      '{count} relations entrantes referencent cette entite.',
    '{count} outbound relationships originate from this entity.':
      '{count} relations sortantes partent de cette entite.',
    'Observed tags: {value}.': 'Tags observes : {value}.',
    'No extra classification tags were attached.':
      "Aucun tag de classification supplementaire n a ete attache.",
    'Current score: {value}.': 'Score actuel : {value}.',
    'Current classification signals: {value}.': 'Signaux de classification actuels : {value}.',
    'Current classification is based on the entity profile only.':
      "La classification actuelle repose uniquement sur le profil de l entite.",
    'Owner context: {value}.': 'Contexte owner : {value}.',
    'No explicit owner was recorded for this entity.':
      "Aucun owner explicite n a ete enregistre pour cette entite.",
    'Current risk score: {value}.': 'Score de risque actuel : {value}.',
    '{inbound} inbound and {outbound} outbound relationships contribute to the current exposure graph.':
      '{inbound} relations entrantes et {outbound} relations sortantes contribuent au graphe d exposition actuel.',
    'Important context: {value}.': 'Contexte important : {value}.',
    'No special tags amplified the risk context for this entity.':
      "Aucun tag special n a amplifie le contexte de risque pour cette entite.",
    'avg {average} ms | p95 {p95} ms': 'moyenne {average} ms | p95 {p95} ms',
    '{count} runs': '{count} executions',
    'Enterprise posture': 'Posture enterprise',
    Storage: 'Stockage',
    Search: 'Recherche',
    Cache: 'Cache',
    Analytics: 'Analytique',
    connected: 'connecte',
    'not connected': 'non connecte',
    'Operational details': 'Details operationnels',
    'Operational Flow': 'Flux operationnel',
    'Readiness and next actions': 'Preparation et prochaines actions',
    'Overall status': 'Statut global',
    Completion: 'Completion',
    'Open actions': 'Actions ouvertes',
    Ready: 'Pret',
    'Recommended next actions': 'Prochaines actions recommandees',
    'Operational readiness is calculated after authentication.':
      'La preparation operationnelle est calculee apres l authentification.',
    Connectors: 'Connecteurs',
    'Official integration posture': "Posture officielle d integration",
    '{count} entities': '{count} entites',
    '{count} links': '{count} liens',
    'Supported entities': 'Entites supportees',
    'Required environment': 'Environnement requis',
    'Required permissions': 'Permissions requises',
    'Linked identities': 'Identites liees',
    'Load JSON file': 'Charger un fichier JSON',
    'Bundle JSON': 'Bundle JSON',
    'Importing...': 'Import en cours...',
    'Import local source': 'Importer une source locale',
    'Answer who has access and why': 'Repondre a qui a acces et pourquoi',
    'Command Center': 'Centre de commande',
    'Focus on access questions': 'Se concentrer sur les questions d acces',
    'Manage auth, targets and imports': 'Gerer auth, cibles et imports',
    'Manage identities and collection': 'Gerer identites et collecte',
    'Track readiness and performance': 'Suivre la preparation et la performance',
    'What still needs attention': 'Ce qui demande encore de l attention',
    'MVP Readiness': 'Preparation MVP',
    complete: 'termine',
    ready: 'pret',
    'Selected Step': 'Etape selectionnee',
    required: 'obligatoire',
    recommended: 'recommande',
    'Recommended action: {value}': 'Action recommandee : {value}',
    'Data freshness: {value}': 'Fraicheur des donnees : {value}',
    'Open relevant section': 'Ouvrir la section correspondante',
    'Blockers: {value}': 'Blocages : {value}',
    Active: 'Actif',
    Configured: 'Configure',
    Attention: 'Attention',
    Disabled: 'Desactive',
    Optional: 'Optionnel',
    Healthy: 'Sain',
    Critical: 'Critique',
    Info: 'Info',
    'Live collector': 'Collecteur live',
    'Partial runtime': 'Runtime partiel',
    'Blueprint only': 'Blueprint uniquement',
    Auto: 'Auto',
    'SSH remote': 'SSH distant',
    'Local path': 'Chemin local',
    Pending: 'En attente',
    disabled: 'desactive',
    enabled: 'active',
    'n/d': 'n/d',
    completed: 'termine',
    warning: 'alerte',
    idle: 'inactif',
    Freshness: 'Fraicheur',
    'privileged principals': 'principaux privilegies',
    'delegated paths': 'chemins delegues',
    'Most exposed resources': 'Ressources les plus exposees',
    'No exposure hotspot is available yet.':
      'Aucun point chaud d exposition n est encore disponible.',
    'Risk Dashboard': 'Tableau de bord risque',
    'Top risk findings': 'Principaux findings de risque',
    'No risk finding is available yet.':
      'Aucun finding de risque n est encore disponible.',
    'Hidden Admin Rights': 'Droits admin caches',
    'Indirect privileged paths': 'Chemins privilegies indirects',
    Findings: 'Findings',
    'Suggested cleanups': 'Nettoyages suggeres',
    'No hidden admin right is currently flagged.':
      'Aucun droit admin cache n est actuellement signale.',
    'Recently Changed Access': 'Acces modifies recemment',
    'Latest processing events': 'Derniers evenements de traitement',
    'No recent platform change is available yet.':
      'Aucun changement recent de plateforme n est disponible.',
    'Access Overview': 'Vue d ensemble des acces',
    'Grants and paths': 'Grants et chemins',
    'Risk Findings': 'Findings de risque',
    'Change History': 'Historique des changements',
    'User view': 'Vue utilisateur',
    'Resource view': 'Vue ressource',
    'Direct Grants': 'Grants directs',
    'Inherited Grants': 'Grants herites',
    'Group Paths': 'Chemins de groupe',
    'Role Paths': 'Chemins de role',
    'Admin Rights': 'Droits administrateur',
    Kind: 'Type',
    Criticality: 'Criticite',
    'No entity selected': 'Aucune entite selectionnee',
    'No direct grant is currently modeled for this entity.':
      'Aucun grant direct n est actuellement modele pour cette entite.',
    'No inherited grant is currently modeled for this entity.':
      'Aucun grant herite n est actuellement modele pour cette entite.',
    'Inheritance Chain': 'Chaine d heritage',
    'No resource hierarchy closure is currently materialized for this entity.':
      'Aucune fermeture de la hierarchie des ressources n est actuellement materialisee pour cette entite.',
    'No group path is currently modeled for this entity.':
      'Aucun chemin de groupe n est actuellement modele pour cette entite.',
    'Effective Groups': 'Groupes effectifs',
    Depth: 'Profondeur',
    Parent: 'Parent',
    'No effective group closure is currently materialized for this entity.':
      'Aucune fermeture effective des groupes n est actuellement materialisee pour cette entite.',
    'No role path is currently modeled for this entity.':
      'Aucun chemin de role n est actuellement modele pour cette entite.',
    'No risk finding is currently linked to this entity.':
      'Aucun finding de risque n est actuellement lie a cette entite.',
    'No recent change was recorded for the current environment.':
      'Aucun changement recent n a ete enregistre pour l environnement actuel.',
    'Why this entity matters': 'Pourquoi cette entite compte',
    'How criticality is interpreted': 'Comment la criticite est interpretee',
    'Criticality is the business importance score assigned by the normalization pipeline. Higher values usually indicate entities tied to sensitive resources, privileged routes or important operational scope.':
      'La criticite est le score d importance metier attribue par la pipeline de normalisation. Des valeurs plus elevees indiquent en general des entites liees a des ressources sensibles, des chemins privilegies ou un perimetre operationnel important.',
    'Why the risk score is elevated': 'Pourquoi le score de risque est eleve',
    'Risk is derived from effective permissions, privilege indicators, indirect grant paths and breadth of exposure. It is meant to explain urgency, not hide it behind a black-box score.':
      'Le risque derive des permissions effectives, des indicateurs de privilege, des chemins de grant indirects et de l ampleur de l exposition. Il sert a expliquer l urgence, pas a la cacher derriere un score opaque.',
    'Select any entity to inspect its neighborhood.':
      'Selectionnez une entite pour inspecter son environnement.',
    '{value} is broadly exposed': '{value} est largement expose',
    '{principal} reaches {resource} with privileged rights':
      '{principal} atteint {resource} avec des droits privilegies',
    '{value} grants privileged access to a broad membership':
      '{value} accorde un acces privilegie a une large appartenance',
    '{principal} reaches {resource} through deep nesting':
      '{principal} atteint {resource} via un nesting profond',
    '{principals} privileged principals currently reach this resource.':
      '{principals} principaux privilegies atteignent actuellement cette ressource.',
    'This entitlement is currently materialized as privileged effective access in the index.':
      'Ce droit est actuellement materialise dans l index comme acces effectif privilegie.',
    '{principals} direct members are currently covered by this privileged group path.':
      '{principals} membres directs sont actuellement couverts par ce chemin de groupe privilegie.',
    'This access depends on multiple nested groups before the effective grant is applied.':
      'Cet acces depend de plusieurs groupes imbriques avant que le grant effectif soit applique.',
    '{status} scan processed {resources} resources and {relationships} relationships across {targets} targets.':
      'Le scan en etat {status} a traite {resources} ressources et {relationships} relations sur {targets} cibles.',
    'Real feature coverage': 'Couverture reelle des fonctionnalites',
    'What the app really does today': "Ce que l'application fait vraiment aujourd'hui",
    present: 'present',
    partial: 'partiel',
    missing: 'manquant',
    'Required gaps': 'Ecarts obligatoires',
    'Capability inventory': 'Inventaire des capacites',
    'Gap: {value}': 'Ecart : {value}',
    'Feature inventory becomes available after the first authenticated refresh.':
      "L'inventaire des fonctionnalites devient disponible apres le premier rafraichissement authentifie.",
    'Check your authenticator code to complete the sign-in.':
      "Verifiez le code de votre application d'authentification pour terminer la connexion.",
    'Initial setup completed. The workspace is now ready for your first scan.':
      "La configuration initiale est terminee. L'espace de travail est maintenant pret pour le premier scan.",
    'Password updated. Sign in again to continue.':
      'Mot de passe mis a jour. Reconnectez-vous pour continuer.',
    'MFA secret generated. Add it to your authenticator app, then confirm it with a TOTP code.':
      "Secret MFA genere. Ajoutez-le a votre application d'authentification puis confirmez-le avec un code TOTP.",
    'MFA enabled successfully for the local account.':
      'La MFA a ete activee avec succes pour le compte local.',
    'Authentication provider created. You can now enable it for sign-in.':
      "Fournisseur d'authentification cree. Vous pouvez maintenant l'activer pour la connexion.",
    'Authentication provider disabled.': "Fournisseur d'authentification desactive.",
    'Authentication provider enabled.': "Fournisseur d'authentification active.",
    'Authentication provider removed.': "Fournisseur d'authentification supprime.",
    'Target scan completed. The workspace has been refreshed with the latest data.':
      "Le scan de la cible est termine. L'espace de travail a ete actualise avec les donnees les plus recentes.",
    'Full scan completed. The workspace has been refreshed with the latest data.':
      "Le scan complet est termine. L'espace de travail a ete actualise avec les donnees les plus recentes.",
    'Target disabled.': 'Cible desactivee.',
    'Target enabled.': 'Cible activee.',
    'Target added. Run a scan when you are ready to collect live data.':
      'Cible ajoutee. Lancez un scan lorsque vous etes pret a collecter des donnees en direct.',
    'Source bundle imported and merged into the workspace.':
      "Paquet source importe et fusionne dans l'espace de travail.",
    'Imported source disabled.': 'Source importee desactivee.',
    'Imported source enabled.': 'Source importee activee.',
    'Imported source removed from the workspace.':
      "Source importee retiree de l'espace de travail.",
    'Import file loaded into the editor. Review it before importing.':
      "Fichier d'import charge dans l'editeur. Verifiez-le avant l'import.",
    'Benchmark completed. Review the latest collection and query timings.':
      'Benchmark termine. Verifiez les derniers temps de collecte et de requete.',
    'Pilot launchpad': 'Parcours pilote',
    'Walk the shortest path from setup to first evidence':
      'Suivez le chemin le plus court entre la configuration et la premiere preuve',
    'Use this guided flow to complete the minimum viable setup, collect the first live snapshot, validate explainability and produce evidence an operator can trust.':
      "Utilisez ce flux guide pour terminer la configuration minimale, collecter le premier instantane en direct, valider l'explicabilite et produire des preuves fiables pour les operateurs.",
    'Step-by-step rollout': 'Deploiement pas a pas',
    'Open next guided step': "Ouvrir l'etape guidee suivante",
    'Freshness: {value}': 'Fraicheur : {value}',
    'Last successful scan: {value}': 'Dernier scan reussi : {value}',
    'Raw batches: {value}': 'Lots bruts : {value}',
    'Index rows: {value}': "Lignes d'index : {value}",
    fresh: 'frais',
    stale: 'obsolete',
    empty: 'vide',
    'Use the recommended action below to keep the MVP rollout moving and generate your first trustworthy evidence.':
      'Utilisez l action recommandee ci-dessous pour faire avancer le deploiement MVP et produire votre premiere preuve fiable.',
    'Bootstrap administrator': 'Administrateur initial',
    'Authentication plane': "Plan d'authentification",
    'Local administrator MFA': 'MFA administrateur local',
    'Target coverage': 'Couverture des cibles',
    'Raw ingestion and normalization': 'Ingestion brute et normalisation',
    'Materialized access index': "Index d'acces materialise",
    'Connector readiness': 'Preparation des connecteurs',
    'Governance and evidence': 'Gouvernance et preuves',
    'Proceed with the current administrator account.':
      "Poursuivez avec le compte administrateur actuel.",
    'Keep local admin as break-glass and review provider scopes periodically.':
      'Conservez un administrateur local comme compte de secours et revisez regulierement les scopes des fournisseurs.',
    'Optionally configure LDAP or OAuth2/OIDC for delegated operator access.':
      "Configurez eventuellement LDAP ou OAuth2/OIDC pour l'acces delegue des operateurs.",
    'Keep a monitored break-glass account and review MFA recovery procedures.':
      'Conservez un compte de secours surveille et revisez les procedures de recuperation MFA.',
    'Enable built-in TOTP MFA for local administrators, or rely on Keycloak/OIDC MFA for federated operators.':
      'Activez la MFA TOTP integree pour les administrateurs locaux ou utilisez la MFA Keycloak/OIDC pour les operateurs federes.',
    'Review target depth and connector coverage.':
      'Revoyez la profondeur des cibles et la couverture des connecteurs.',
    'Add at least one monitored filesystem target or import an offline source bundle.':
      'Ajoutez au moins une cible filesystem surveillee ou importez un paquet source hors ligne.',
    'Monitor snapshot freshness and raw retention.':
      'Surveillez la fraicheur des snapshots et la retention brute.',
    'Run a scan to populate raw ingestion and normalized entities.':
      'Lancez un scan pour alimenter l ingestion brute et les entites normalisees.',
    'Use indexed access APIs for fast explain and exposure queries.':
      "Utilisez les API d'acces indexe pour des requetes rapides d'explication et d'exposition.",
    'Complete a scan so the entitlement compiler can populate the access index.':
      "Terminez un scan afin que le compilateur d'entitlements puisse remplir l'index d'acces.",
    'Keep connector credentials rotated and monitor failures.':
      'Faites tourner les identifiants des connecteurs et surveillez les echecs.',
    'Configure official connector environments for the identity or cloud surfaces you need.':
      'Configurez les environnements officiels des connecteurs pour les surfaces identite ou cloud dont vous avez besoin.',
    'Use review campaigns and remediation plans as the operational decision loop.':
      'Utilisez les campagnes de revue et les plans de remediation comme boucle de decision operationnelle.',
    'Create a first review campaign so the evidence and remediation workflow is exercised.':
      'Creez une premiere campagne de revue afin de faire vivre le workflow de preuve et de remediation.',
    failed: 'echec',
    success: 'succes',
    healthy: 'sain',
    running: 'en cours',
  },
  es: {
    Language: 'Idioma',
    English: 'Ingles',
    Italian: 'Italiano',
    German: 'Aleman',
    French: 'Frances',
    Spanish: 'Espanol',
    Home: 'Inicio',
    Investigate: 'Investigar',
    Govern: 'Gobierno',
    Sources: 'Fuentes',
    Operations: 'Operaciones',
    Explain: 'Explicar',
    Exposure: 'Exposicion',
    'What-If': 'What-If',
    Reviews: 'Revisiones',
    Remediation: 'Remediacion',
    Auth: 'Autenticacion',
    Collection: 'Recopilacion',
    Imports: 'Importaciones',
    Identity: 'Identidad',
    Status: 'Estado',
    Platform: 'Plataforma',
    Audit: 'Auditoria',
    Navigation: 'Navegacion',
    'Section Menu': 'Menu de seccion',
    'Open a module': 'Abrir un modulo',
    'Universal search': 'Busqueda universal',
    'Search users, groups, roles, folders, mailboxes, vaults...':
      'Buscar usuarios, grupos, roles, carpetas, buzones, vaults...',
    'Searching the graph...': 'Buscando en el grafo...',
    'No matching identity or resource.': 'No hay identidad o recurso coincidente.',
    'Select a user or resource to update the live access views.':
      'Selecciona un usuario o recurso para actualizar las vistas de acceso en vivo.',
    'Question Studio': 'Question Studio',
    'Why does this access exist?': 'Por que existe este acceso?',
    Principal: 'Principal',
    Resource: 'Recurso',
    Permissions: 'Permisos',
    Paths: 'Rutas',
    Risk: 'Riesgo',
    'Access Map': 'Mapa de acceso',
    'Clean path view for the selected entitlement':
      'Vista limpia de la ruta para el permiso seleccionado',
    'Each lane shows the effective route from identity to resource, with one transition per step.':
      'Cada carril muestra la ruta efectiva desde la identidad hasta el recurso, con una transicion por paso.',
    Nodes: 'Nodos',
    Links: 'Enlaces',
    Pipeline: 'Pipeline',
    'Index refresh': 'Actualizacion del indice',
    Mode: 'Modo',
    'Reused rows': 'Filas reutilizadas',
    'Recomputed rows': 'Filas recalculadas',
    'Impacted principals': 'Principales afectados',
    'Impacted resources': 'Recursos afectados',
    'Group closure refresh': 'Actualizacion del cierre de grupos',
    'Hierarchy refresh': 'Actualizacion de la jerarquia',
    'Carry-forward': 'Reutilizado',
    Existing: 'Existente',
    Delta: 'Delta',
    'Full rebuild': 'Reconstruccion completa',
    'Previous snapshot: {value}': 'Snapshot anterior: {value}',
    'The next successful scan will publish an index refresh summary.':
      'El proximo escaneo correcto publicara un resumen de la actualizacion del indice.',
    'Access index refresh uses carry-forward when the graph is unchanged and delta recomputation when the impacted scope stays small.':
      'La actualizacion del indice de acceso reutiliza el estado previo cuando el grafo no cambia y usa recomputacion delta cuando el alcance afectado sigue siendo pequeno.',
    Rows: 'Filas',
    Previous: 'Anterior',
    Next: 'Siguiente',
    'Focused Entity': 'Entidad enfocada',
    'Why this matters': 'Por que importa',
    'Selected resource': 'Recurso seleccionado',
    principals: 'principales',
    'Monitored Targets': 'Objetivos monitorizados',
    'Filesystem scope': 'Alcance del filesystem',
    'Target name': 'Nombre del objetivo',
    'Filesystem path': 'Ruta del filesystem',
    Connection: 'Conexion',
    'Local / mounted': 'Local / montado',
    'Remote Linux via SSH': 'Linux remoto por SSH',
    'Latest Scan': 'Ultimo escaneo',
    'Operational status': 'Estado operativo',
    Finished: 'Finalizado',
    Duration: 'Duracion',
    Warnings: 'Advertencias',
    Governance: 'Gobernanza',
    'Access reviews': 'Revisiones de acceso',
    Scope: 'Alcance',
    Action: 'Accion',
    Progress: 'Progreso',
    'Workspace sections': 'Secciones del workspace',
    Workspace: 'Espacio de trabajo',
    'Workspace: {value}': 'Espacio de trabajo: {value}',
    'Organizations and environments': 'Organizaciones y entornos',
    'Use dedicated workspaces to isolate a customer, business unit or environment while keeping authentication and platform administration in one control plane.':
      'Usa espacios de trabajo dedicados para aislar un cliente, una unidad de negocio o un entorno manteniendo autenticacion y administracion de la plataforma en un mismo plano de control.',
    'Update active workspace': 'Actualizar el espacio activo',
    'Workspace name': 'Nombre del espacio',
    'Save workspace details': 'Guardar detalles del espacio',
    'Create workspace': 'Crear espacio',
    'Workspace activated. The control plane has been refreshed.':
      'Espacio activado. El plano de control se ha actualizado.',
    'Workspace created. Switch to it when you are ready to isolate another organization or environment.':
      'Espacio creado. Cambia a el cuando quieras aislar otra organizacion o entorno.',
    'Workspace details updated.': 'Detalles del espacio actualizados.',
    'Unable to activate the workspace.': 'No se pudo activar el espacio.',
    'Unable to create the workspace.': 'No se pudo crear el espacio.',
    'Unable to update the workspace.': 'No se pudo actualizar el espacio.',
    Slug: 'Slug',
    'On-prem': 'On-prem',
    Hybrid: 'Hibrido',
    Cloud: 'Cloud',
    'Investigation graph': 'Grafo de investigacion',
    'Dense neighborhood view for the focused entity':
      'Vista densa del vecindario para la entidad enfocada',
    'Use the dense graph to inspect nearby grants, memberships and inherited routes without collapsing everything into a single path.':
      'Usa el grafo denso para inspeccionar grants cercanos, membresias y rutas heredadas sin colapsarlo todo en una sola ruta.',
    'No investigation graph is available for this focus yet.':
      'Todavia no hay un grafo de investigacion disponible para este foco.',
    'Open investigation graph': 'Abrir grafo de investigacion',
    'Hide investigation graph': 'Ocultar grafo de investigacion',
    Density: 'Densidad',
    Compact: 'Compacto',
    Expanded: 'Ampliado',
    'Loading current page...': 'Cargando pagina actual...',
    'Loading access window...': 'Cargando ventana de acceso...',
    'This investigation graph is currently capped to {nodes} nodes and {edges} links so the view stays responsive.':
      'Este grafo de investigacion esta limitado a {nodes} nodos y {edges} enlaces para mantener la vista fluida.',
    'Start from a short operational dashboard with top exposure, quick actions and recent platform signals before drilling into a workflow.':
      'Empieza con un panel operativo corto con exposicion principal, acciones rapidas y senales recientes de la plataforma antes de entrar en un flujo de trabajo.',
    'Use the explain, exposure and what-if views to answer who has access, why it exists and what changes would do.':
      'Usa las vistas explain, exposure y what-if para responder quien tiene acceso, por que existe y que cambiaria una modificacion.',
    'Keep decisions, revoke plans and review evidence together so the governance loop stays clear and deterministic.':
      'Mantiene juntas las decisiones, los planes de revocacion y la evidencia de revision para que el ciclo de gobierno siga siendo claro y determinista.',
    'Configure administrators, sign-in providers, monitored targets, offline bundles and cross-source identity linking in one place.':
      'Configura administradores, proveedores de acceso, objetivos monitorizados, bundles offline y vinculacion de identidades entre fuentes en un solo lugar.',
    'Monitor scan health, runtime posture, connector readiness, benchmarks and administrator activity without cluttering the investigation flow.':
      'Supervisa la salud de los escaneos, la postura runtime, el estado de los conectores, los benchmarks y la actividad administrativa sin ensuciar el flujo de investigacion.',
    'Offline Sources': 'Fuentes offline',
    'Import local JSON bundles': 'Importar bundles JSON locales',
    'Identity Fabric': 'Identity Fabric',
    'Cross-source linked identities': 'Identidades vinculadas entre fuentes',
    'Combined access footprint': 'Huella de acceso combinada',
    '{count} linked identities | {permissions}': '{count} identidades vinculadas | {permissions}',
    'Connect at least two identity sources for the same organization to unlock cross-source correlation and a unified user footprint.':
      'Conecta al menos dos fuentes de identidad de la misma organizacion para habilitar la correlacion entre fuentes y una huella unificada del usuario.',
    'confidence {value}': 'confianza {value}',
    Performance: 'Rendimiento',
    'Real local benchmark': 'Benchmark local real',
    'Running...': 'Ejecutando...',
    Targets: 'Objetivos',
    'Run the live benchmark on demand so normal workspace loading stays fast.':
      'Ejecuta el benchmark en vivo solo bajo demanda para que la carga normal del workspace siga siendo rapida.',
    'Official Blueprint': 'Blueprint oficial',
    'Cloud and IAM integration notes': 'Notas de integracion cloud e IAM',
    Runtime: 'Runtime',
    Limitation: 'Limitacion',
    'Official documentation': 'Documentacion oficial',
    'Audit Trail': 'Rastro de auditoria',
    'Recent administrator actions': 'Acciones recientes del administrador',
    'No audit event has been recorded yet.': 'Todavia no se ha registrado ningun evento de auditoria.',
    'Platform posture becomes available after administrator authentication.':
      'La postura de la plataforma estara disponible despues de la autenticacion del administrador.',
    '{kind} discovered from {source} in the {environment} estate.':
      '{kind} descubierto desde {source} en el entorno {environment}.',
    '{count} inbound relationships reference this entity.':
      '{count} relaciones entrantes hacen referencia a esta entidad.',
    '{count} outbound relationships originate from this entity.':
      '{count} relaciones salientes parten de esta entidad.',
    'Observed tags: {value}.': 'Etiquetas observadas: {value}.',
    'No extra classification tags were attached.':
      'No se adjuntaron etiquetas de clasificacion adicionales.',
    'Current score: {value}.': 'Puntuacion actual: {value}.',
    'Current classification signals: {value}.': 'Senales actuales de clasificacion: {value}.',
    'Current classification is based on the entity profile only.':
      'La clasificacion actual se basa solo en el perfil de la entidad.',
    'Owner context: {value}.': 'Contexto del owner: {value}.',
    'No explicit owner was recorded for this entity.':
      'No se registro un owner explicito para esta entidad.',
    'Current risk score: {value}.': 'Puntuacion de riesgo actual: {value}.',
    '{inbound} inbound and {outbound} outbound relationships contribute to the current exposure graph.':
      '{inbound} relaciones entrantes y {outbound} relaciones salientes contribuyen al grafo actual de exposicion.',
    'Important context: {value}.': 'Contexto importante: {value}.',
    'No special tags amplified the risk context for this entity.':
      'Ninguna etiqueta especial amplio el contexto de riesgo de esta entidad.',
    'avg {average} ms | p95 {p95} ms': 'media {average} ms | p95 {p95} ms',
    '{count} runs': '{count} ejecuciones',
    'Enterprise posture': 'Postura enterprise',
    Storage: 'Almacenamiento',
    Search: 'Busqueda',
    Cache: 'Cache',
    Analytics: 'Analitica',
    connected: 'conectado',
    'not connected': 'no conectado',
    'Operational details': 'Detalles operativos',
    'Operational Flow': 'Flujo operativo',
    'Readiness and next actions': 'Preparacion y proximas acciones',
    'Overall status': 'Estado general',
    Completion: 'Completado',
    'Open actions': 'Acciones abiertas',
    Ready: 'Listo',
    'Recommended next actions': 'Proximas acciones recomendadas',
    'Operational readiness is calculated after authentication.':
      'La preparacion operativa se calcula despues de la autenticacion.',
    Connectors: 'Conectores',
    'Official integration posture': 'Postura oficial de integracion',
    '{count} entities': '{count} entidades',
    '{count} links': '{count} enlaces',
    'Supported entities': 'Entidades compatibles',
    'Required environment': 'Entorno requerido',
    'Required permissions': 'Permisos requeridos',
    'Linked identities': 'Identidades vinculadas',
    'Load JSON file': 'Cargar archivo JSON',
    'Bundle JSON': 'Bundle JSON',
    'Importing...': 'Importando...',
    'Import local source': 'Importar fuente local',
    'Answer who has access and why': 'Responder quien tiene acceso y por que',
    'Command Center': 'Centro de mando',
    'Focus on access questions': 'Centrarse en las preguntas de acceso',
    'Manage auth, targets and imports': 'Gestionar auth, objetivos e importaciones',
    'Manage identities and collection': 'Gestionar identidades y recopilacion',
    'Track readiness and performance': 'Seguir preparacion y rendimiento',
    'What still needs attention': 'Lo que todavia necesita atencion',
    'MVP Readiness': 'Preparacion MVP',
    complete: 'completo',
    ready: 'listo',
    'Selected Step': 'Paso seleccionado',
    required: 'obligatorio',
    recommended: 'recomendado',
    'Recommended action: {value}': 'Accion recomendada: {value}',
    'Data freshness: {value}': 'Frescura de los datos: {value}',
    'Open relevant section': 'Abrir la seccion relevante',
    'Blockers: {value}': 'Bloqueos: {value}',
    Active: 'Activo',
    Configured: 'Configurado',
    Attention: 'Atencion',
    Disabled: 'Desactivado',
    Optional: 'Opcional',
    Healthy: 'Sano',
    Critical: 'Critico',
    Info: 'Info',
    'Live collector': 'Colector live',
    'Partial runtime': 'Runtime parcial',
    'Blueprint only': 'Solo blueprint',
    Auto: 'Auto',
    'SSH remote': 'SSH remoto',
    'Local path': 'Ruta local',
    Pending: 'Pendiente',
    disabled: 'desactivado',
    enabled: 'activado',
    'n/d': 'n/d',
    completed: 'completado',
    warning: 'aviso',
    idle: 'inactivo',
    Freshness: 'Frescura',
    'privileged principals': 'principales privilegiados',
    'delegated paths': 'rutas delegadas',
    'Most exposed resources': 'Recursos mas expuestos',
    'No exposure hotspot is available yet.':
      'Todavia no hay un punto caliente de exposicion disponible.',
    'Risk Dashboard': 'Panel de riesgo',
    'Top risk findings': 'Principales findings de riesgo',
    'No risk finding is available yet.':
      'Todavia no hay ningun finding de riesgo disponible.',
    'Hidden Admin Rights': 'Derechos admin ocultos',
    'Indirect privileged paths': 'Rutas privilegiadas indirectas',
    Findings: 'Findings',
    'Suggested cleanups': 'Limpiezas sugeridas',
    'No hidden admin right is currently flagged.':
      'Actualmente no hay ningun derecho admin oculto marcado.',
    'Recently Changed Access': 'Accesos cambiados recientemente',
    'Latest processing events': 'Ultimos eventos de procesamiento',
    'No recent platform change is available yet.':
      'No hay ningun cambio reciente de plataforma disponible.',
    'Access Overview': 'Resumen de acceso',
    'Grants and paths': 'Grants y rutas',
    'Risk Findings': 'Findings de riesgo',
    'Change History': 'Historial de cambios',
    'User view': 'Vista de usuario',
    'Resource view': 'Vista de recurso',
    'Direct Grants': 'Grants directos',
    'Inherited Grants': 'Grants heredados',
    'Group Paths': 'Rutas de grupo',
    'Role Paths': 'Rutas de rol',
    'Admin Rights': 'Derechos administrativos',
    Kind: 'Tipo',
    Criticality: 'Criticidad',
    'No entity selected': 'No hay entidad seleccionada',
    'No direct grant is currently modeled for this entity.':
      'Actualmente no hay ningun grant directo modelado para esta entidad.',
    'No inherited grant is currently modeled for this entity.':
      'Actualmente no hay ningun grant heredado modelado para esta entidad.',
    'Inheritance Chain': 'Cadena de herencia',
    'No resource hierarchy closure is currently materialized for this entity.':
      'Actualmente no hay un cierre de la jerarquia de recursos materializado para esta entidad.',
    'No group path is currently modeled for this entity.':
      'Actualmente no hay ninguna ruta de grupo modelada para esta entidad.',
    'Effective Groups': 'Grupos efectivos',
    Depth: 'Profundidad',
    Parent: 'Padre',
    'No effective group closure is currently materialized for this entity.':
      'Actualmente no hay un cierre efectivo de grupos materializado para esta entidad.',
    'No role path is currently modeled for this entity.':
      'Actualmente no hay ninguna ruta de rol modelada para esta entidad.',
    'No risk finding is currently linked to this entity.':
      'Actualmente no hay ningun finding de riesgo vinculado a esta entidad.',
    'No recent change was recorded for the current environment.':
      'No se registro ningun cambio reciente para el entorno actual.',
    'Why this entity matters': 'Por que importa esta entidad',
    'How criticality is interpreted': 'Como se interpreta la criticidad',
    'Criticality is the business importance score assigned by the normalization pipeline. Higher values usually indicate entities tied to sensitive resources, privileged routes or important operational scope.':
      'La criticidad es la puntuacion de importancia de negocio asignada por la canalizacion de normalizacion. Los valores mas altos suelen indicar entidades vinculadas a recursos sensibles, rutas privilegiadas o un alcance operativo importante.',
    'Why the risk score is elevated': 'Por que la puntuacion de riesgo es elevada',
    'Risk is derived from effective permissions, privilege indicators, indirect grant paths and breadth of exposure. It is meant to explain urgency, not hide it behind a black-box score.':
      'El riesgo se deriva de los permisos efectivos, los indicadores de privilegio, las rutas indirectas de grant y la amplitud de la exposicion. Su objetivo es explicar la urgencia, no ocultarla detras de una puntuacion opaca.',
    'Select any entity to inspect its neighborhood.':
      'Selecciona cualquier entidad para inspeccionar su entorno.',
    '{value} is broadly exposed': '{value} esta ampliamente expuesto',
    '{principal} reaches {resource} with privileged rights':
      '{principal} alcanza {resource} con derechos privilegiados',
    '{value} grants privileged access to a broad membership':
      '{value} concede acceso privilegiado a una membresia amplia',
    '{principal} reaches {resource} through deep nesting':
      '{principal} alcanza {resource} mediante nesting profundo',
    '{principals} privileged principals currently reach this resource.':
      '{principals} principales privilegiados alcanzan actualmente este recurso.',
    'This entitlement is currently materialized as privileged effective access in the index.':
      'Este derecho esta actualmente materializado en el indice como acceso efectivo privilegiado.',
    '{principals} direct members are currently covered by this privileged group path.':
      '{principals} miembros directos estan actualmente cubiertos por esta ruta de grupo privilegiada.',
    'This access depends on multiple nested groups before the effective grant is applied.':
      'Este acceso depende de varios grupos anidados antes de que se aplique el grant efectivo.',
    '{status} scan processed {resources} resources and {relationships} relationships across {targets} targets.':
      'El escaneo en estado {status} proceso {resources} recursos y {relationships} relaciones en {targets} objetivos.',
    'Real feature coverage': 'Cobertura real de funcionalidades',
    'What the app really does today': 'Lo que la aplicacion hace realmente hoy',
    present: 'presente',
    partial: 'parcial',
    missing: 'faltante',
    'Required gaps': 'Brechas obligatorias',
    'Capability inventory': 'Inventario de capacidades',
    'Gap: {value}': 'Brecha: {value}',
    'Feature inventory becomes available after the first authenticated refresh.':
      'El inventario de funcionalidades estara disponible despues del primer refresco autenticado.',
    'Check your authenticator code to complete the sign-in.':
      'Comprueba el codigo de tu aplicacion autenticadora para completar el acceso.',
    'Initial setup completed. The workspace is now ready for your first scan.':
      'La configuracion inicial ha terminado. El espacio de trabajo ya esta listo para el primer escaneo.',
    'Password updated. Sign in again to continue.':
      'Contrasena actualizada. Vuelve a iniciar sesion para continuar.',
    'MFA secret generated. Add it to your authenticator app, then confirm it with a TOTP code.':
      'Se ha generado el secreto MFA. Anadelo a tu aplicacion autenticadora y confirmalo con un codigo TOTP.',
    'MFA enabled successfully for the local account.':
      'La MFA se ha activado correctamente para la cuenta local.',
    'Authentication provider created. You can now enable it for sign-in.':
      'Proveedor de autenticacion creado. Ahora puedes habilitarlo para el acceso.',
    'Authentication provider disabled.': 'Proveedor de autenticacion deshabilitado.',
    'Authentication provider enabled.': 'Proveedor de autenticacion habilitado.',
    'Authentication provider removed.': 'Proveedor de autenticacion eliminado.',
    'Target scan completed. The workspace has been refreshed with the latest data.':
      'El escaneo del objetivo ha terminado. El espacio de trabajo se ha actualizado con los datos mas recientes.',
    'Full scan completed. The workspace has been refreshed with the latest data.':
      'El escaneo completo ha terminado. El espacio de trabajo se ha actualizado con los datos mas recientes.',
    'Target disabled.': 'Objetivo deshabilitado.',
    'Target enabled.': 'Objetivo habilitado.',
    'Target added. Run a scan when you are ready to collect live data.':
      'Objetivo agregado. Ejecuta un escaneo cuando estes listo para recopilar datos en vivo.',
    'Source bundle imported and merged into the workspace.':
      'Paquete de origen importado y fusionado en el espacio de trabajo.',
    'Imported source disabled.': 'Origen importado deshabilitado.',
    'Imported source enabled.': 'Origen importado habilitado.',
    'Imported source removed from the workspace.':
      'Origen importado eliminado del espacio de trabajo.',
    'Import file loaded into the editor. Review it before importing.':
      'Archivo de importacion cargado en el editor. Revisalo antes de importarlo.',
    'Benchmark completed. Review the latest collection and query timings.':
      'Benchmark completado. Revisa los ultimos tiempos de recopilacion y consulta.',
    'Pilot launchpad': 'Ruta guiada del piloto',
    'Walk the shortest path from setup to first evidence':
      'Recorre el camino mas corto desde la configuracion hasta la primera evidencia',
    'Use this guided flow to complete the minimum viable setup, collect the first live snapshot, validate explainability and produce evidence an operator can trust.':
      'Usa este flujo guiado para completar la configuracion minima viable, recopilar el primer snapshot en vivo, validar la explicabilidad y producir evidencias en las que el operador pueda confiar.',
    'Step-by-step rollout': 'Despliegue paso a paso',
    'Open next guided step': 'Abrir el siguiente paso guiado',
    'Freshness: {value}': 'Frescura: {value}',
    'Last successful scan: {value}': 'Ultimo escaneo correcto: {value}',
    'Raw batches: {value}': 'Lotes raw: {value}',
    'Index rows: {value}': 'Filas del indice: {value}',
    fresh: 'fresco',
    stale: 'obsoleto',
    empty: 'vacio',
    'Use the recommended action below to keep the MVP rollout moving and generate your first trustworthy evidence.':
      'Usa la accion recomendada de abajo para mantener el despliegue MVP en marcha y generar tu primera evidencia fiable.',
    'Bootstrap administrator': 'Administrador inicial',
    'Authentication plane': 'Plano de autenticacion',
    'Local administrator MFA': 'MFA del administrador local',
    'Target coverage': 'Cobertura de objetivos',
    'Raw ingestion and normalization': 'Ingestion en bruto y normalizacion',
    'Materialized access index': 'Indice materializado de accesos',
    'Connector readiness': 'Preparacion de conectores',
    'Governance and evidence': 'Gobierno y evidencias',
    'Proceed with the current administrator account.':
      'Continua con la cuenta de administrador actual.',
    'Keep local admin as break-glass and review provider scopes periodically.':
      'Manten al administrador local como cuenta de emergencia y revisa periodicamente los alcances del proveedor.',
    'Optionally configure LDAP or OAuth2/OIDC for delegated operator access.':
      'Configura opcionalmente LDAP u OAuth2/OIDC para el acceso delegado de operadores.',
    'Keep a monitored break-glass account and review MFA recovery procedures.':
      'Manten una cuenta de emergencia monitorizada y revisa los procedimientos de recuperacion MFA.',
    'Enable built-in TOTP MFA for local administrators, or rely on Keycloak/OIDC MFA for federated operators.':
      'Habilita la MFA TOTP integrada para administradores locales o apoya la MFA de Keycloak/OIDC para operadores federados.',
    'Review target depth and connector coverage.':
      'Revisa la profundidad de los objetivos y la cobertura de los conectores.',
    'Add at least one monitored filesystem target or import an offline source bundle.':
      'Agrega al menos un objetivo de filesystem monitorizado o importa un paquete de origen offline.',
    'Monitor snapshot freshness and raw retention.':
      'Supervisa la frescura de los snapshots y la retencion raw.',
    'Run a scan to populate raw ingestion and normalized entities.':
      'Ejecuta un escaneo para poblar la ingesta en bruto y las entidades normalizadas.',
    'Use indexed access APIs for fast explain and exposure queries.':
      'Usa las API de acceso indexado para consultas rapidas de explicacion y exposicion.',
    'Complete a scan so the entitlement compiler can populate the access index.':
      'Completa un escaneo para que el compilador de entitlement pueda poblar el indice de acceso.',
    'Keep connector credentials rotated and monitor failures.':
      'Manten rotadas las credenciales de los conectores y supervisa los fallos.',
    'Configure official connector environments for the identity or cloud surfaces you need.':
      'Configura los entornos oficiales de conectores para las superficies de identidad o cloud que necesites.',
    'Use review campaigns and remediation plans as the operational decision loop.':
      'Usa campanas de revision y planes de remediacion como ciclo operativo de decision.',
    'Create a first review campaign so the evidence and remediation workflow is exercised.':
      'Crea una primera campana de revision para ejercitar el flujo de evidencias y remediacion.',
    failed: 'fallido',
    success: 'correcto',
    healthy: 'saludable',
    running: 'en ejecucion',
  },
}

const dynamicTranslations: Record<LocaleCode, DynamicRule[]> = {
  en: [],
  it: [
    { pattern: /^(\d+) groups included$/, render: (count) => `${count} gruppi inclusi` },
    { pattern: /^(\d+) active collectors$/, render: (count) => `${count} collector attivi` },
    { pattern: /^(\d+) delegated$/, render: (count) => `${count} delegati` },
    { pattern: /^(\d+) deny entries modeled$/, render: (count) => `${count} deny modellati` },
    { pattern: /^(\d+) principals$/, render: (count) => `${count} principali` },
    { pattern: /^(\d+) privileged$/, render: (count) => `${count} privilegiati` },
    { pattern: /^Scan enabled targets$/, render: () => 'Scansiona i target attivi' },
  ],
  de: [
    { pattern: /^(\d+) groups included$/, render: (count) => `${count} Gruppen enthalten` },
    { pattern: /^(\d+) active collectors$/, render: (count) => `${count} aktive Kollektoren` },
    { pattern: /^(\d+) delegated$/, render: (count) => `${count} delegiert` },
    { pattern: /^(\d+) deny entries modeled$/, render: (count) => `${count} Deny-Eintraege modelliert` },
    { pattern: /^(\d+) principals$/, render: (count) => `${count} Prinzipale` },
    { pattern: /^(\d+) privileged$/, render: (count) => `${count} privilegiert` },
  ],
  fr: [
    { pattern: /^(\d+) groups included$/, render: (count) => `${count} groupes inclus` },
    { pattern: /^(\d+) active collectors$/, render: (count) => `${count} collecteurs actifs` },
    { pattern: /^(\d+) delegated$/, render: (count) => `${count} delegues` },
    { pattern: /^(\d+) deny entries modeled$/, render: (count) => `${count} regles deny modelisees` },
    { pattern: /^(\d+) principals$/, render: (count) => `${count} principaux` },
    { pattern: /^(\d+) privileged$/, render: (count) => `${count} privilegies` },
  ],
  es: [
    { pattern: /^(\d+) groups included$/, render: (count) => `${count} grupos incluidos` },
    { pattern: /^(\d+) active collectors$/, render: (count) => `${count} recolectores activos` },
    { pattern: /^(\d+) delegated$/, render: (count) => `${count} delegados` },
    { pattern: /^(\d+) deny entries modeled$/, render: (count) => `${count} entradas deny modeladas` },
    { pattern: /^(\d+) principals$/, render: (count) => `${count} principales` },
    { pattern: /^(\d+) privileged$/, render: (count) => `${count} privilegiados` },
  ],
}

const localeFormats: Record<LocaleCode, string> = {
  en: 'en-US',
  it: 'it-IT',
  de: 'de-DE',
  fr: 'fr-FR',
  es: 'es-ES',
}

const languageOptions: Array<{ code: LocaleCode; label: string }> = [
  { code: 'en', label: 'English' },
  { code: 'it', label: 'Italian' },
  { code: 'de', label: 'German' },
  { code: 'fr', label: 'French' },
  { code: 'es', label: 'Spanish' },
]

const I18nContext = createContext<I18nValue | null>(null)

function detectInitialLocale(): LocaleCode {
  const saved = typeof window !== 'undefined' ? window.localStorage.getItem(STORAGE_KEY) : null
  if (saved && ['en', 'it', 'de', 'fr', 'es'].includes(saved)) {
    return saved as LocaleCode
  }
  const browserLocale = typeof navigator !== 'undefined' ? navigator.language.slice(0, 2) : 'en'
  if (['en', 'it', 'de', 'fr', 'es'].includes(browserLocale)) {
    return browserLocale as LocaleCode
  }
  return 'en'
}

function interpolate(template: string, params?: Record<string, string | number | null | undefined>) {
  if (!params) {
    return template
  }
  return template.replace(/\{(\w+)\}/g, (_, key: string) => {
    const value = params[key]
    return value === null || value === undefined ? '' : String(value)
  })
}

function translateDynamic(locale: LocaleCode, source: string) {
  for (const rule of dynamicTranslations[locale]) {
    const match = source.match(rule.pattern)
    if (match) {
      return rule.render(...match.slice(1))
    }
  }
  return source
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<LocaleCode>(detectInitialLocale)

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, locale)
    document.documentElement.lang = locale
  }, [locale])

  const value = useMemo<I18nValue>(() => {
    const t = (source: string, params?: Record<string, string | number | null | undefined>) => {
      const translated =
        locale === 'en'
          ? source
          : translations[locale][source] ?? translateDynamic(locale, source)
      return interpolate(translated, params)
    }

    return {
      locale,
      setLocale: setLocaleState,
      t,
      formatDateTime: (value?: string | null) => {
        if (!value) {
          return t('n/d')
        }
        return new Intl.DateTimeFormat(localeFormats[locale], {
          dateStyle: 'medium',
          timeStyle: 'short',
        }).format(new Date(value))
      },
      formatDate: (value?: string | null) => {
        if (!value) {
          return t('n/d')
        }
        return new Intl.DateTimeFormat(localeFormats[locale], {
          dateStyle: 'medium',
        }).format(new Date(value))
      },
      languageOptions: languageOptions.map((option) => ({
        code: option.code,
        label: t(option.label),
      })),
    }
  }, [locale])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const context = useContext(I18nContext)
  if (!context) {
    throw new Error('useI18n must be used inside I18nProvider')
  }
  return context
}
