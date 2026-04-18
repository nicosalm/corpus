<script lang="ts">
	import { Marked } from 'marked';
	import DOMPurify from 'dompurify';
	import katex from 'katex';
	import 'katex/dist/katex.min.css';

	interface Props {
		content: string;
	}

	let { content }: Props = $props();

	const renderer = {
		heading({ text, depth }: { text: string; depth: number }) {
			const level = Math.min(depth + 1, 6);
			return `<h${level}>${text}</h${level}>`;
		}
	};

	const marked = new Marked({
		breaks: false,
		gfm: true,
		renderer
	});

	function renderLatex(text: string): string {
		text = text.replace(/\$\$([\s\S]+?)\$\$/g, (_match, tex: string) => {
			try {
				return katex.renderToString(tex.trim(), {
					displayMode: true,
					throwOnError: false,
					output: 'htmlAndMathml'
				});
			} catch {
				return `<code class="katex-error">${tex}</code>`;
			}
		});

		text = text.replace(/(?<!\$)\$(?!\$)((?:[^$\\]|\\.)+?)\$(?!\$)/g, (_match, tex: string) => {
			try {
				return katex.renderToString(tex.trim(), {
					displayMode: false,
					throwOnError: false,
					output: 'htmlAndMathml'
				});
			} catch {
				return `<code class="katex-error">${tex}</code>`;
			}
		});

		return text;
	}

	let rendered = $derived.by(() => {
		const withLatex = renderLatex(content);
		const html = marked.parse(withLatex) as string;

		const clean = DOMPurify.sanitize(html, {
			ADD_TAGS: ['math', 'mrow', 'mi', 'mo', 'mn', 'msup', 'msub', 'mfrac', 'msqrt',
				'mover', 'munder', 'munderover', 'mtable', 'mtr', 'mtd', 'mtext',
				'mspace', 'semantics', 'annotation'],
			ADD_ATTR: ['xmlns', 'encoding', 'mathvariant', 'stretchy', 'fence', 'separator',
				'accent', 'accentunder', 'columnalign', 'rowalign', 'columnspacing',
				'rowspacing', 'displaystyle', 'scriptlevel', 'aria-hidden', 'focusable',
				'role', 'style', 'width', 'height', 'viewBox', 'preserveAspectRatio'],
			FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'form'],
			FORBID_ATTR: ['onerror', 'onclick', 'onload', 'onmouseover']
		});

		return clean;
	});
</script>

<div class="markdown">
	{@html rendered}
</div>

<style>
	.markdown {
		line-height: var(--lh);
	}

	.markdown :global(:first-child) {
		margin-top: 0;
	}

	.markdown :global(pre) {
		background: var(--code-bg);
		padding: 0.5rem 0.75rem;
		border-left: 2px solid var(--border);
		overflow-x: auto;
		margin: 0.5rem 0;
		font-size: var(--fs-small);
	}

	.markdown :global(pre code) {
		background: none;
		padding: 0;
	}

	.markdown :global(blockquote) {
		margin: 0.5rem 0;
		padding: 0.4rem 0.75rem;
		background: var(--code-bg);
		border-left: 2px solid var(--border);
	}

	.markdown :global(table) {
		border-collapse: collapse;
		margin: 0.5rem 0;
		font-size: var(--fs-small);
	}

	.markdown :global(th),
	.markdown :global(td) {
		border: 1px solid var(--border-light);
		padding: 0.3rem 0.5rem;
	}

	.markdown :global(th) {
		background: var(--code-bg);
		font-weight: 700;
	}

	.markdown :global(.katex-display) {
		margin: 0.5rem 0;
		overflow-x: auto;
	}

	.markdown :global(.katex-error) {
		color: #c00;
	}
</style>
