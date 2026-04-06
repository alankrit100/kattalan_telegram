<script>
  import '../app.css';
  import { onMount } from 'svelte';

  let channelInput = '';
  let timeframe = '1_month';
  let phase = 'idle'; // idle | loading | complete | error
  let progress = 0;
  let statusText = '';
  let results = null;

  // Memoized ticker bar — generated once on mount, not on every reactive update
  let tickers = [];
  onMount(() => {
    tickers = ['NSE', 'BSE', 'NIFTY50', 'BANKNIFTY', 'GOLD', 'SENSEX', 'USDINR'].map(sym => ({
      sym,
      pct: (Math.random() * 5 + 0.1).toFixed(2),
    }));
  });

  const timeframeOptions = [
    { value: '1_month',  label: '1 Month'  },
    { value: '3_months', label: '3 Months' },
    { value: '6_months', label: '6 Months' },
  ];

  let _ws = null;
  let _timeoutHandle = null;
  let showSkip = false;

  function startAudit() {
    if (!channelInput.trim()) return;
    phase = 'loading';
    progress = 0;
    statusText = 'Initialising connection...';
    results = null;
    showSkip = false;

    _ws = new WebSocket('ws://127.0.0.1:8000/api/ws/audit');

    _ws.onopen = () => {
      _ws.send(JSON.stringify({ channel_input: channelInput.trim(), timeframe }));
      _resetTimeout();
    };

    _ws.onmessage = (event) => {
      let payload;
      try {
        payload = JSON.parse(event.data);
      } catch (err) {
        console.error('Malformed JSON from backend:', event.data, err);
        return;
      }

      progress = payload.progress ?? progress;
      statusText = payload.status ?? statusText;
      _resetTimeout();
      showSkip = false;

      if (payload.progress === 100 && payload.results) {
        results = payload.results;
        phase = 'complete';
        _clearTimeout();
        _ws.close();
      } else if (payload.status && payload.status.startsWith('FATAL ERROR')) {
        phase = 'error';
        _clearTimeout();
        _ws.close();
      }
    };

    _ws.onerror = () => {
      statusText = 'WebSocket error — is the backend running?';
      phase = 'error';
      _clearTimeout();
    };

    _ws.onclose = () => {
      if (phase === 'loading') {
        phase = 'error';
        statusText = 'Connection closed unexpectedly.';
        _clearTimeout();
      }
    };
  }

  function skipChannel() {
    showSkip = false;
    _clearTimeout();
    if (_ws) { try { _ws.close(); } catch (_) {} }
    phase = 'error';
    statusText = 'Channel skipped (timeout).';
  }

  function _resetTimeout() {
    _clearTimeout();
    _timeoutHandle = setTimeout(() => {
      if (phase === 'loading') showSkip = true;
    }, 60_000);
  }

  function _clearTimeout() {
    if (_timeoutHandle) { clearTimeout(_timeoutHandle); _timeoutHandle = null; }
  }

  $: gradeIsGreen = results?.color_grade === 'green';
  $: cardClass    = gradeIsGreen ? 'card-green' : 'card-red';
  $: gradeAccent  = gradeIsGreen ? 'text-green-400' : 'text-red-400';
  $: borderColor  = gradeIsGreen ? 'rgba(34,197,94,0.7)' : 'rgba(239,68,68,0.7)';
</script>

<div class="min-h-screen bg-slate-900 flex flex-col items-center px-4 pb-20">

  <header class="w-full max-w-4xl pt-10 pb-8 flex items-center justify-between border-b border-slate-700/50">
    <div class="flex flex-col">
      <span class="font-mono text-xs tracking-[0.3em] text-slate-500 uppercase mb-1">Admin Terminal v2.1</span>
      <h1 class="font-sans text-2xl font-bold tracking-tight text-slate-100">
        Kattalan <span class="bg-gradient-to-r from-sky-400 to-violet-400 bg-clip-text text-transparent">Quant Engine</span>
      </h1>
    </div>
    <div class="flex items-center gap-2.5 bg-slate-800/60 border border-slate-700/60 rounded-full px-4 py-2">
      <div class="dot-online"></div>
      <span class="font-mono text-xs text-green-400 tracking-widest uppercase">System Online</span>
    </div>
  </header>

  <main class="w-full max-w-4xl mt-10 flex flex-col gap-6">

    <!-- Ticker bar (stable — generated once on mount) -->
    <div class="scanner-line w-full border border-slate-800 rounded-lg bg-slate-800/30 px-5 py-2.5 flex gap-8 overflow-hidden">
      {#each tickers as t}
        <span class="font-mono text-xs text-slate-500 whitespace-nowrap">
          {t.sym} <span class="text-slate-600">·</span>
          <span class="text-green-500/70">{t.pct}%</span>
        </span>
      {/each}
    </div>

    <!-- Input -->
    <section class="bg-slate-800/50 border border-slate-700/60 rounded-2xl p-6 backdrop-blur-sm">
      <div class="mb-5">
        <p class="font-mono text-xs text-slate-500 uppercase tracking-widest mb-1">&gt; CHANNEL_AUDIT_INIT</p>
        <p class="font-sans text-sm text-slate-400">Enter a Telegram channel name, @username, or -100 ID to begin AI evaluation.</p>
      </div>
      <div class="flex flex-col sm:flex-row gap-3">
        <div class="relative flex-1">
          <span class="absolute left-3.5 top-1/2 -translate-y-1/2 font-mono text-slate-500 text-sm select-none">@</span>
          <input id="channel-input" type="text" bind:value={channelInput}
            placeholder="Name, @username, or -100 ID" disabled={phase === 'loading'}
            class="w-full bg-slate-900 border border-slate-600/70 rounded-lg pl-8 pr-4 py-3 font-mono text-sm text-slate-100
                   placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-sky-500/50 focus:border-sky-500/60
                   disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"/>
        </div>
        <div class="relative">
          <select id="timeframe-select" bind:value={timeframe} disabled={phase === 'loading'}
            class="appearance-none bg-slate-900 border border-slate-600/70 rounded-lg px-4 pr-9 py-3 font-mono text-sm
                   text-slate-300 focus:outline-none focus:ring-2 focus:ring-sky-500/50 focus:border-sky-500/60
                   disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 cursor-pointer">
            {#each timeframeOptions as opt}
              <option value={opt.value}>{opt.label}</option>
            {/each}
          </select>
          <svg class="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none"
               fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/>
          </svg>
        </div>
        <button id="audit-btn" on:click={startAudit}
          disabled={phase === 'loading' || !channelInput.trim()}
          class="relative px-6 py-3 rounded-lg font-mono text-sm font-semibold tracking-wider uppercase
                 bg-gradient-to-r from-sky-500 to-violet-600 text-white hover:from-sky-400 hover:to-violet-500
                 disabled:from-slate-700 disabled:to-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed
                 transition-all duration-300 shadow-lg hover:shadow-sky-500/30 active:scale-95 whitespace-nowrap">
          {#if phase === 'loading'}
            <svg class="w-4 h-4 animate-spin inline-block mr-2 -mt-0.5" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
            Auditing...
          {:else}
            &#9654; Audit Channel
          {/if}
        </button>
      </div>
    </section>

    <!-- Progress / Error panel -->
    {#if phase === 'loading' || phase === 'error'}
      <section class="bg-slate-800/40 border border-slate-700/50 rounded-2xl p-6 backdrop-blur-sm">
        <div class="flex items-center gap-2 mb-4">
          <div class="w-2.5 h-2.5 rounded-full bg-red-500/80"></div>
          <div class="w-2.5 h-2.5 rounded-full bg-yellow-500/80"></div>
          <div class="w-2.5 h-2.5 rounded-full bg-green-500/80"></div>
          <span class="font-mono text-xs text-slate-600 ml-2 tracking-widest">KATTALAN_ENGINE — AUDIT_LOG</span>
        </div>
        <div class="w-full h-2 bg-slate-700/60 rounded-full overflow-hidden mb-4">
          {#if phase === 'error'}
            <div class="h-full bg-red-500 rounded-full transition-all duration-500" style="width:{progress}%"></div>
          {:else}
            <div class="h-full rounded-full progress-shimmer transition-all duration-500" style="width:{progress}%"></div>
          {/if}
        </div>
        <div class="flex items-baseline justify-between">
          <p class="font-mono text-xs {phase === 'error' ? 'text-red-400' : 'text-sky-400'} tracking-wide">
            &gt; {statusText}
          </p>
          <span class="font-mono text-lg font-bold {phase === 'error' ? 'text-red-400/80' : 'text-slate-300'}">
            {progress}<span class="text-xs text-slate-500">%</span>
          </span>
        </div>

        <!-- 60s timeout skip button -->
        {#if showSkip}
          <div class="mt-4 flex items-center gap-3 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
            <span class="font-mono text-xs text-yellow-400">Progress stalled &gt; 60s</span>
            <button on:click={skipChannel}
              class="ml-auto font-mono text-xs px-3 py-1 rounded border border-yellow-500/50 text-yellow-400
                     hover:bg-yellow-500/20 transition-colors">
              Skip Channel
            </button>
          </div>
        {/if}

        {#if phase === 'loading'}
          <div class="mt-4 space-y-1.5">
            {#each [1,2,3] as i}
              <div class="h-1 rounded bg-slate-700/40 overflow-hidden">
                <div class="h-full w-1/3 bg-gradient-to-r from-transparent via-sky-500/20 to-transparent
                            animate-[scan_2s_ease-in-out_{i*0.3}s_infinite]"></div>
              </div>
            {/each}
          </div>
        {/if}
      </section>
    {/if}

    <!-- Result card -->
    {#if phase === 'complete' && results}
      <section class="fade-in border rounded-2xl p-6 backdrop-blur-sm relative overflow-hidden {cardClass}"
        style="background:linear-gradient(135deg,{gradeIsGreen?'rgba(34,197,94,0.06)':'rgba(239,68,68,0.06)'} 0%,rgba(15,23,42,0.95) 60%)">
        <div class="absolute top-0 left-0 right-0 h-px"
             style="background:linear-gradient(90deg,transparent,{borderColor},transparent)"></div>

        <div class="flex items-start justify-between mb-6">
          <div>
            <p class="font-mono text-xs text-slate-500 uppercase tracking-widest mb-1">// AUDIT_RESULT — COMPLETE</p>
            <h2 class="font-mono text-xl font-bold text-slate-100">{results.channel_name}</h2>
            <p class="font-mono text-xs text-slate-600 mt-0.5">{results.total_messages_scraped} messages scraped</p>
          </div>
          <div class="flex flex-col items-end gap-1">
            <span class="font-mono text-xs uppercase tracking-widest {gradeAccent}">
              {gradeIsGreen ? '▲ EDGE POSITIVE' : '▼ EDGE NEGATIVE'}
            </span>
            <div class="w-2.5 h-2.5 rounded-full {gradeIsGreen ? 'bg-green-400' : 'bg-red-400'}"
                 style="box-shadow:0 0 8px {gradeIsGreen?'rgba(34,197,94,0.9)':'rgba(239,68,68,0.9)'}"></div>
          </div>
        </div>

        <!-- Primary metrics -->
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
          <div class="bg-slate-900/60 border border-slate-700/50 rounded-xl p-4">
            <p class="font-mono text-xs text-slate-500 uppercase tracking-widest mb-2">Trades Decided</p>
            <p class="font-mono text-3xl font-bold text-slate-100 tabular-nums">{results.total_trades}</p>
          </div>
          <div class="bg-slate-900/60 border border-slate-700/50 rounded-xl p-4">
            <p class="font-mono text-xs text-slate-500 uppercase tracking-widest mb-2">Win Rate</p>
            <p class="font-mono text-3xl font-bold {gradeAccent} tabular-nums">{results.win_rate_pct.toFixed(1)}%</p>
          </div>
          <div class="bg-slate-900/60 border border-slate-700/50 rounded-xl p-4">
            <p class="font-mono text-xs text-slate-500 uppercase tracking-widest mb-2">Edge Ratio</p>
            <p class="font-mono text-3xl font-bold {gradeAccent} tabular-nums">
              {results.edge_ratio > 0 ? '+' : ''}{results.edge_ratio.toFixed(2)}
            </p>
          </div>
        </div>

        <!-- Secondary metrics -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          {#each [
            { label: 'Wins',       val: results.total_wins,       color: 'text-green-400' },
            { label: 'Losses',     val: results.total_losses,     color: 'text-red-400' },
            { label: 'Squared Off',val: results.total_squared_off,color: 'text-yellow-400' },
            { label: 'Expired',    val: results.total_expired,    color: 'text-slate-400' },
          ] as m}
            <div class="bg-slate-900/40 border border-slate-700/40 rounded-lg p-3">
              <p class="font-mono text-xs text-slate-600 uppercase tracking-widest mb-1">{m.label}</p>
              <p class="font-mono text-xl font-bold {m.color} tabular-nums">{m.val}</p>
            </div>
          {/each}
        </div>

        <!-- MFE / MAE -->
        <div class="grid grid-cols-2 gap-3 mb-5">
          <div class="bg-slate-900/40 border border-slate-700/40 rounded-lg p-3">
            <p class="font-mono text-xs text-slate-600 uppercase tracking-widest mb-1">Avg MFE (pts)</p>
            <p class="font-mono text-lg font-bold text-green-400/80 tabular-nums">{results.avg_mfe.toFixed(2)}</p>
          </div>
          <div class="bg-slate-900/40 border border-slate-700/40 rounded-lg p-3">
            <p class="font-mono text-xs text-slate-600 uppercase tracking-widest mb-1">Avg MAE (pts)</p>
            <p class="font-mono text-lg font-bold text-red-400/80 tabular-nums">{results.avg_mae.toFixed(2)}</p>
          </div>
        </div>

        <div class="pt-4 border-t border-slate-700/40 flex items-center justify-between">
          <span class="font-mono text-xs text-slate-600">
            Saved to Supabase · {new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}
          </span>
          <button on:click={() => { phase='idle'; results=null; channelInput=''; }}
            class="font-mono text-xs text-slate-500 hover:text-sky-400 transition-colors duration-200 underline underline-offset-2">
            &#8635; New Audit
          </button>
        </div>
      </section>
    {/if}

  </main>

  <footer class="w-full max-w-4xl mt-auto pt-12 border-t border-slate-800/60 flex justify-between items-center">
    <span class="font-mono text-xs text-slate-700 tracking-widest uppercase">Kattalan Engine © {new Date().getFullYear()}</span>
    <span class="font-mono text-xs text-slate-700">ws://127.0.0.1:8000/api/ws/audit</span>
  </footer>

</div>