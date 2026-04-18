<script lang="ts">
	import { onMount } from 'svelte';
	import {
		forceSimulation,
		forceLink,
		forceManyBody,
		forceCenter,
		forceCollide,
		type SimulationNodeDatum,
		type SimulationLinkDatum
	} from 'd3-force';
	import type { ConceptGraph, ConceptNode as ApiNode, ConceptEdge as ApiEdge } from '$lib/api';

	interface Props {
		graph: ConceptGraph;
	}

	let { graph }: Props = $props();

	interface GraphNode extends SimulationNodeDatum {
		id: string;
		name: string;
	}

	interface GraphLink extends SimulationLinkDatum<GraphNode> {
		weight: number | null;
	}

	let svgEl: SVGSVGElement;
	let nodes = $state<GraphNode[]>([]);
	let links = $state<GraphLink[]>([]);
	let width = 500;
	let height = 300;

	let draggedNode = $state<GraphNode | null>(null);
	let panOffset = $state({ x: 0, y: 0 });
	let isPanning = $state(false);
	let panStart = { x: 0, y: 0 };
	let zoom = $state(1);

	let simulation: ReturnType<typeof forceSimulation<GraphNode>> | null = null;

	let viewBox = $derived(
		`${-panOffset.x / zoom} ${-panOffset.y / zoom} ${width / zoom} ${height / zoom}`
	);

	onMount(() => {
		const graphNodes: GraphNode[] = graph.nodes.map((n: ApiNode) => ({
			id: n.name,
			name: n.name
		}));

		const nodeIds = new Set(graphNodes.map((n: GraphNode) => n.id));
		const graphLinks: GraphLink[] = graph.edges
			.filter((e: ApiEdge) => nodeIds.has(e.source) && nodeIds.has(e.target))
			.map((e: ApiEdge) => ({
				source: e.source,
				target: e.target,
				weight: e.weight ?? null
			}));

		simulation = forceSimulation(graphNodes)
			.force(
				'link',
				forceLink<GraphNode, GraphLink>(graphLinks)
					.id((d: GraphNode) => d.id)
					.distance(80)
			)
			.force('charge', forceManyBody().strength(-200))
			.force('center', forceCenter(width / 2, height / 2))
			.force('collide', forceCollide(30));

		simulation.on('tick', () => {
			nodes = [...graphNodes];
			links = [...graphLinks];
		});

		return () => simulation?.stop();
	});

	function getX(node: GraphNode | string): number {
		if (typeof node === 'string') return width / 2;
		return node.x ?? width / 2;
	}

	function getY(node: GraphNode | string): number {
		if (typeof node === 'string') return height / 2;
		return node.y ?? height / 2;
	}

	function svgPoint(e: MouseEvent): { x: number; y: number } {
		const rect = svgEl.getBoundingClientRect();
		return {
			x: ((e.clientX - rect.left) / rect.width) * (width / zoom) - panOffset.x / zoom,
			y: ((e.clientY - rect.top) / rect.height) * (height / zoom) - panOffset.y / zoom
		};
	}

	function handleMouseDown(e: MouseEvent, node?: GraphNode) {
		if (node) {
			draggedNode = node;
			node.fx = node.x;
			node.fy = node.y;
			simulation?.alphaTarget(0.3).restart();
		} else {
			isPanning = true;
			panStart = { x: e.clientX - panOffset.x, y: e.clientY - panOffset.y };
		}
		e.preventDefault();
	}

	function handleMouseMove(e: MouseEvent) {
		if (draggedNode) {
			const pt = svgPoint(e);
			draggedNode.fx = pt.x;
			draggedNode.fy = pt.y;
		} else if (isPanning) {
			panOffset = { x: e.clientX - panStart.x, y: e.clientY - panStart.y };
		}
	}

	function handleMouseUp() {
		if (draggedNode) {
			draggedNode.fx = null;
			draggedNode.fy = null;
			draggedNode = null;
			simulation?.alphaTarget(0);
		}
		isPanning = false;
	}

	function handleWheel(e: WheelEvent) {
		e.preventDefault();
		const factor = e.deltaY > 0 ? 0.9 : 1.1;
		zoom = Math.max(0.3, Math.min(3, zoom * factor));
	}
</script>

<details class="graph-details" open>
	<summary>concept graph ({graph.nodes.length} nodes, {graph.edges.length} edges)</summary>
	<div class="graph-container">
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<svg
			bind:this={svgEl}
			viewBox={viewBox}
			onmousedown={(e) => handleMouseDown(e)}
			onmousemove={handleMouseMove}
			onmouseup={handleMouseUp}
			onmouseleave={handleMouseUp}
			onwheel={handleWheel}
			class:grabbing={isPanning || draggedNode !== null}
		>
			{#each links as link}
				<line
					x1={getX(link.source as GraphNode)}
					y1={getY(link.source as GraphNode)}
					x2={getX(link.target as GraphNode)}
					y2={getY(link.target as GraphNode)}
					stroke="var(--border)"
					stroke-width="1"
				/>
			{/each}
			{#each nodes as node}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<g
					class="node-group"
					onmousedown={(e) => {
						e.stopPropagation();
						handleMouseDown(e, node);
					}}
				>
					<circle cx={node.x} cy={node.y} r="5" class="node-circle" />
					<text x={(node.x ?? 0) + 8} y={(node.y ?? 0) + 3} class="node-label">
						{node.name}
					</text>
				</g>
			{/each}
		</svg>
	</div>
</details>

<style>
	.graph-details {
		margin-bottom: 0.75rem;
		font-size: var(--fs-small);
	}

	summary {
		cursor: pointer;
		color: var(--text-secondary);
		user-select: none;
	}

	summary:hover {
		color: var(--text);
	}

	.graph-container {
		margin-top: 0.5rem;
		border: 1px solid var(--border-light);
		background: white;
		overflow: hidden;
	}

	svg {
		width: 100%;
		height: 300px;
		cursor: grab;
		display: block;
	}

	svg.grabbing {
		cursor: grabbing;
	}

	.node-group {
		cursor: grab;
	}

	.node-circle {
		fill: var(--text-secondary);
	}

	.node-group:hover .node-circle {
		fill: var(--text);
		r: 6;
	}

	.node-label {
		font-family: var(--font);
		font-size: 10px;
		fill: var(--text);
		pointer-events: none;
		user-select: none;
	}
</style>
