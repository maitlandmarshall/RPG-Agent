
const fs = require('fs');

// --- Random Number Generators ---

function gaussianRandom(mean, stdDev)
{
	let u = 0, v = 0;
	while (u === 0) u = Math.random(); // Converting [0,1) to (0,1)
	while (v === 0) v = Math.random();
	return mean + stdDev * Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
}

function triangular(min, max, mode)
{
	const u = Math.random();
	const c = (mode - min) / (max - min);
	if (u <= c)
	{
		return min + Math.sqrt(u * (max - min) * (mode - min));
	} else
	{
		return max - Math.sqrt((1 - u) * (max - min) * (max - mode));
	}
}

function paretovariate(alpha)
{
	return 1.0 / Math.pow(Math.random(), 1.0 / alpha);
}

// --- Core Mechanics ---

function resolveAction(skillLevel, difficulty, conditions = [])
{
	// Base momentum from skill
	let momentum = skillLevel;

	// Add chaos factor
	const chaos = gaussianRandom(0, 20);

	// Environmental modifiers
	let conditionModifier = 0;
	for (const condition of conditions)
	{
		conditionModifier += (condition.value || 0);
	}
	momentum += conditionModifier;

	// Calculate success margin
	const total = momentum + chaos;
	const margin = total - difficulty;

	// Determine critical
	const criticalThreshold = skillLevel / 2;
	const isCritical = Math.abs(chaos) > criticalThreshold;

	return {
		success: margin >= 0,
		margin: Math.round(margin),
		isCritical: isCritical,
		totalMomentum: Math.round(total),
		chaosFactor: Math.round(chaos),
		details: {
			baseSkill: skillLevel,
			difficulty: difficulty,
			conditionsVal: conditionModifier
		}
	};
}

// --- CLI Handlers ---

function main()
{
	const args = process.argv.slice(2);
	const command = args[0];

	if (command === 'resolve')
	{
		// Usage: node game_engine.js resolve <skill> <difficulty> [condition1=val1] [condition2=val2]
		const skill = parseFloat(args[1]);
		const difficulty = parseFloat(args[2]);
		const conditions = args.slice(3).map(c =>
		{
			const [name, val] = c.split('=');
			return { name, value: parseFloat(val) };
		});

		console.log(JSON.stringify(resolveAction(skill, difficulty, conditions), null, 2));
	} else if (command === 'weather')
	{
		// Usage: node game_engine.js weather <alpha> <beta>
		const alpha = parseFloat(args[1] || 2);
		const beta = parseFloat(args[2] || 5);

		// Beta variate approximation
		const gamma = (k) =>
		{
			let sum = 0;
			for (let i = 0; i < Math.floor(k); i++) sum += -Math.log(Math.random());
			return sum;
		};
		const x = gamma(alpha);
		const y = gamma(beta);
		const result = x / (x + y);

		console.log(JSON.stringify({ value: result }, null, 2));
	} else
	{
		console.log("Unknown command. Available: resolve, weather");
	}
}

main();
