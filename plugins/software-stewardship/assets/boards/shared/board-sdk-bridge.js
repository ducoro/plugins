// Shared progressive-enhancement bridge for software-stewardship interactive boards.
// Standalone first: works with zero host SDK injection, and activates window.ducoro
// features (Composer draft staging, live cast, shared view storage, agent commands,
// live file revalidation, and read-only preview / shot projection) when served in a Ducoro Space.

export function createBoardBridge({
  boardId,
  defaultView = {},
  onData = () => {},
  onApplyView = () => {},
  getView = () => ({}),
  commands = {},
}) {
  const sdk = globalThis.ducoro ?? null;
  let linkState = sdk ? 'connecting' : 'standalone';
  let latestActors = [];
  let currentDataRaw = '';
  let statusEl = null;

  const isShot = () =>
    document.documentElement.dataset.ducoroRender === 'shot' ||
    sdk?.board?.context?.renderMode === 'shot';

  const isProjection = () => Boolean(sdk?.ui?.projection);

  const isNonEmbedded = () => sdk?.board?.context?.embedded === false;

  const canUseComposer = () =>
    Boolean(sdk?.composer?.draft) &&
    linkState === 'connected' &&
    !isShot() &&
    !isProjection() &&
    !isNonEmbedded();

  function setStatus(message, tone = 'info') {
    if (!statusEl) return;
    statusEl.textContent = message;
    statusEl.dataset.tone = tone;
    statusEl.hidden = !message;
  }

  function updateWriteControls() {
    const writable = canUseComposer();
    const showSdkButtons = Boolean(sdk) && !isShot() && !isProjection() && !isNonEmbedded();
    for (const btn of document.querySelectorAll('[data-requires-sdk]')) {
      if (!showSdkButtons) {
        btn.hidden = true;
      } else {
        btn.hidden = false;
        btn.disabled = !writable || btn.dataset.busy === 'true';
      }
    }
  }

  function readInlineData() {
    const el = document.getElementById('board-initial-data');
    if (!el) return null;
    try {
      const raw = el.textContent.trim();
      if (!raw) return null;
      currentDataRaw = raw;
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }

  async function fetchFreshData({ throwOnError = false } = {}) {
    try {
      const res = await fetch('./assets/data.json', { cache: 'no-store' });
      if (!res.ok) {
        if (throwOnError) throw new Error(`HTTP ${res.status} fetching assets/data.json`);
        return null;
      }
      const raw = (await res.text()).trim();
      const parsed = JSON.parse(raw);
      return { raw, parsed };
    } catch (error) {
      if (throwOnError) throw error;
      return null;
    }
  }

  function preferredLeadActor() {
    return (
      latestActors.find((a) => a.kind === 'agent' && a.lead) ||
      latestActors.find((a) => a.kind === 'agent') ||
      null
    );
  }

  function formatMention(actor) {
    const safeLabel = String(actor.name || actor.id).replace(/[\[\]]/g, '');
    const safeId = encodeURIComponent(String(actor.id));
    return `[@${safeLabel}](mention://agent/${safeId})`;
  }

  async function stageDraft(text, buttonEl = null) {
    if (!canUseComposer()) {
      setStatus('Composer staging requires an embedded, connected Space session.', 'warn');
      return false;
    }
    const lead = preferredLeadActor();
    const wireText = lead && !text.includes('mention://')
      ? `${formatMention(lead)} ${text}`
      : text;

    if (buttonEl) {
      buttonEl.dataset.busy = 'true';
      buttonEl.disabled = true;
    }
    try {
      await sdk.composer.draft(wireText);
      setStatus('Draft staged in Composer. Review and press Send to authorize.', 'ok');
      return true;
    } catch (error) {
      const code = error?.code ? ` (${error.code})` : '';
      const hint = error?.hint || (error?.code === 'host_recovering'
        ? 'Workspace data is still recovering; try again shortly.'
        : error?.code === 'read_only'
          ? 'Board is currently in read-only mode.'
          : 'Check Space connection and try again.');
      setStatus(`Could not stage draft${code}: ${hint}`, 'error');
      return false;
    } finally {
      if (buttonEl) {
        delete buttonEl.dataset.busy;
      }
      updateWriteControls();
    }
  }

  async function persistView() {
    if (!sdk || isShot() || isProjection() || linkState !== 'connected') return;
    try {
      await sdk.board.ready;
      if (!sdk.board.canIUse?.('storage.set')) return;
      await sdk.storage.set('view', { ...defaultView, ...getView() });
    } catch (error) {
      const code = error?.code ? ` (${error.code})` : '';
      const hint = error?.hint || 'Local view state remains active.';
      setStatus(`View preference was not saved${code}: ${hint}`, 'warn');
    }
  }

  function registerSdkLifecycle() {
    if (!sdk) return;

    sdk.ui?.onLinkChange?.(({ state }) => {
      linkState = state;
      updateWriteControls();
      if (state === 'reconnecting' || state === 'disconnected') {
        setStatus(`Connection ${state}. Read-only browsing continues; write controls paused.`, 'warn');
      } else if (state === 'connected') {
        setStatus('', 'info');
      }
    });

    sdk.space?.onCastChange?.(({ actors }) => {
      latestActors = Array.isArray(actors) ? actors : [];
    });

    if (!isShot() && !isProjection() && sdk.board?.commands && Object.keys(commands).length > 0) {
      void sdk.board.commands(commands).catch((error) => {
        const code = error?.code ? ` (${error.code})` : '';
        setStatus(`Board view commands could not register${code}. Reload if commands are required.`, 'warn');
      });
    }

    if (sdk.board?.revalidate) {
      sdk.board.revalidate(async (notice, context) => {
        if (notice.reason === 'files' && notice.scope === 'all') {
          return { status: 'reload-required', reason: 'full_scope_change' };
        }
        const paths = (notice.changes || []).flatMap((c) => [c.path, c.from, c.to].filter(Boolean));
        const runtimeTouched = paths.some((p) => p === 'index.html' || p.startsWith('runtime/'));
        if (notice.reason === 'files' && runtimeTouched) {
          return { status: 'reload-required', reason: 'runtime_changed' };
        }
        const fresh = await fetchFreshData({ throwOnError: true });
        if (!context.isCurrent()) return { status: 'deferred' };
        if (fresh && fresh.raw !== currentDataRaw) {
          currentDataRaw = fresh.raw;
          onData(fresh.parsed);
        }
        return { status: 'applied' };
      });
    }
  }

  async function start() {
    statusEl = document.querySelector('[data-bridge-status]');
    const inlineData = readInlineData();
    if (inlineData) onData(inlineData);

    // Register SDK subscriptions, commands, and revalidation synchronously before network fetches
    // so early READY handshakes and top-level command declarations are never missed.
    registerSdkLifecycle();
    updateWriteControls();

    const fetched = await fetchFreshData({ throwOnError: false });
    if (fetched && fetched.raw !== currentDataRaw) {
      currentDataRaw = fetched.raw;
      onData(fetched.parsed);
    }

    if (!sdk) return;
    try {
      await sdk.board.ready;
      updateWriteControls();
      if (!isProjection() && sdk.board.canIUse?.('storage.get')) {
        const saved = await sdk.storage.get('view');
        if (saved && typeof saved === 'object') {
          onApplyView({ ...defaultView, ...saved });
        }
      }
    } catch {
      updateWriteControls();
    }
  }

  return {
    boardId,
    start,
    stageDraft,
    persistView,
    updateWriteControls,
    isShot,
    setStatus,
  };
}
