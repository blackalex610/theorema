import React, { useEffect, useRef, useMemo } from 'react';
import katex from 'katex';
import 'katex/dist/katex.css';

interface MathProps {
	formula: string;
	display?: boolean;
	className?: string;
}

/**
 * Pre-process formula to fix common KaTeX noglyph issues
 */
function cleanFormula(formula: string): string {
	let cleaned = formula;
	
	// Remove \operatorname (not supported by default KaTeX)
	cleaned = cleaned.replace(/\\operatorname\{([^}]+)\}/g, '\\text{$1}');
	
	// Fix Bulgarian trig notation
	cleaned = cleaned.replace(/\\tg(?![a-zA-Z])/g, '\\tan');
	cleaned = cleaned.replace(/\\ctg(?![a-zA-Z])/g, '\\cot');
	cleaned = cleaned.replace(/\\arctg(?![a-zA-Z])/g, '\\arctan');
	cleaned = cleaned.replace(/\\arcctg(?![a-zA-Z])/g, '\\arccot');
	
	// Replace multiplication symbols with \cdot
	cleaned = cleaned.replace(/×/g, '\\cdot ');
	cleaned = cleaned.replace(/·/g, '\\cdot ');
	
	// Remove any remaining Cyrillic characters (they cause noglyph errors)
	cleaned = cleaned.replace(/[а-яА-Я]+/g, '');
	
	// Clean up multiple spaces
	cleaned = cleaned.replace(/\s+/g, ' ').trim();
	
	return cleaned;
}

export const MathFormula: React.FC<MathProps> = ({ formula, display = false, className = '' }) => {
	const spanRef = useRef<HTMLSpanElement>(null);
	const divRef = useRef<HTMLDivElement>(null);
	
	// Pre-process formula to fix common issues
	const cleanedFormula = useMemo(() => cleanFormula(formula), [formula]);

	useEffect(() => {
		const el = display ? divRef.current : spanRef.current;
		if (!el) return;

		try {
			katex.render(cleanedFormula, el, {
				displayMode: display,
				throwOnError: false,
				trust: false,
				// Add macros for common missing commands
				macros: {
					'\\tg': '\\tan',
					'\\ctg': '\\cot',
					'\\arctg': '\\arctan',
					'\\arcctg': '\\arccot',
				},
			});
		} catch {
			// Fallback: show plain text with styling
			el.textContent = cleanedFormula;
			el.classList.add('font-mono', 'text-sm');
		}
	}, [cleanedFormula, display]);

	return display ? <div ref={divRef} className={className} /> : <span ref={spanRef} className={className} />;
};

function autoWrapInlineLatex(text: string): string {
	if (text.includes('$') || text.includes('\\(') || text.includes('\\[')) return text;

	// Wrap common raw latex fragments so they render nicely.
	// Example: "2025 - 225 \\cdot (-\\frac{1}{5})" -> "2025 - 225 $\\cdot (-\\frac{1}{5})$"
	let result = text;
	result = result.replace(/(\\frac\{[^{}]+\}\{[^{}]+\}|\\sqrt\{[^{}]+\}|\\cdot|\\times|\\div|\^\{[^{}]+\})/g, '$$$1$');

	// Wrap common exponent expressions that arrive without explicit math delimiters.
	// Examples: x^2, m^3, cm^2, (x-4)^2, 20^\\circ, x^{-1}
	result = result.replace(
		/((?:\([^)]+\)|[A-Za-zА-Яа-я0-9]+)\^(?:\{[^{}]+\}|[A-Za-zА-Яа-я0-9]+|\\[a-zA-Z]+))/g,
		'$$1$'
	);

	// Wrap unit exponents like cm^2, m^3 if they were split by whitespace.
	result = result.replace(/((?:cm|mm|dm|m|km)\^(?:\{[^{}]+\}|[0-9]+))/g, '$$$1$');
	return result;
}

export function renderMathText(input: string | undefined | null): React.ReactNode {
	if (!input) return null;

	const text = autoWrapInlineLatex(input);
	const parts: React.ReactNode[] = [];
	let i = 0;
	let key = 0;

	const pushText = (chunk: string) => {
		if (chunk) parts.push(chunk);
	};

	while (i < text.length) {
		const rest = text.slice(i);

		if (rest.startsWith('$$')) {
			const end = text.indexOf('$$', i + 2);
			if (end === -1) {
				pushText(text.slice(i));
				break;
			}
			const formula = text.slice(i + 2, end);
			parts.push(<MathFormula key={`m-${key++}`} formula={formula} display className="my-2" />);
			i = end + 2;
			continue;
		}

		if (rest.startsWith('$')) {
			const end = text.indexOf('$', i + 1);
			if (end === -1) {
				pushText(text.slice(i));
				break;
			}
			const formula = text.slice(i + 1, end);
			parts.push(<MathFormula key={`m-${key++}`} formula={formula} className="inline align-middle" />);
			i = end + 1;
			continue;
		}

		if (rest.startsWith('\\[')) {
			const end = text.indexOf('\\]', i + 2);
			if (end === -1) {
				pushText(text.slice(i));
				break;
			}
			const formula = text.slice(i + 2, end);
			parts.push(<MathFormula key={`m-${key++}`} formula={formula} display className="my-2" />);
			i = end + 2;
			continue;
		}

		if (rest.startsWith('\\(')) {
			const end = text.indexOf('\\)', i + 2);
			if (end === -1) {
				pushText(text.slice(i));
				break;
			}
			const formula = text.slice(i + 2, end);
			parts.push(<MathFormula key={`m-${key++}`} formula={formula} className="inline align-middle" />);
			i = end + 2;
			continue;
		}

		// Plain text until next possible math delimiter.
		const nextPositions = [
			text.indexOf('$$', i),
			text.indexOf('$', i),
			text.indexOf('\\[', i),
			text.indexOf('\\(', i),
		].filter((n) => n >= 0);

		if (nextPositions.length === 0) {
			pushText(text.slice(i));
			break;
		}

		const next = Math.min(...nextPositions);
		pushText(text.slice(i, next));
		i = next;
	}

	return parts;
}

