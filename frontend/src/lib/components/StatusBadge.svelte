<script lang="ts">
	import { onMount } from 'svelte';
	import { getHealth } from '$lib/api';

	let status = $state<'healthy' | 'degraded' | 'offline'>('offline');

	onMount(() => {
		check();
		const interval = setInterval(check, 30_000);
		return () => clearInterval(interval);
	});

	async function check() {
		try {
			const health = await getHealth();
			status = health.status === 'healthy' ? 'healthy' : 'degraded';
		} catch {
			status = 'offline';
		}
	}
</script>

<span class="badge" class:healthy={status === 'healthy'} class:degraded={status === 'degraded'}>
	<span class="dot"></span>
	{status}
</span>

<style>
	.badge {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		font-size: var(--fs-small);
		color: var(--text-secondary);
	}

	.dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: #d44;
	}

	.healthy .dot {
		background: #4a4;
	}

	.degraded .dot {
		background: #da4;
	}
</style>
