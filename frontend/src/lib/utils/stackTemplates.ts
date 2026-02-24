import type { CodebaseContext } from '$lib/api/client';

export interface StackTemplate {
	id: string;
	name: string;
	description: string;
	context: CodebaseContext;
}

export const STACK_TEMPLATES: StackTemplate[] = [
	{
		id: 'sveltekit-ts',
		name: 'SvelteKit + TS',
		description: 'SvelteKit 2 with Svelte 5 runes and TypeScript',
		context: {
			language: 'TypeScript',
			framework: 'SvelteKit 2 / Svelte 5',
			conventions: [
				'Use Svelte 5 runes ($state, $derived, $effect) instead of stores',
				'Co-locate component tests as {Component}.test.ts',
				'Use Tailwind CSS utility classes for styling',
			],
			patterns: [
				'File-based routing under src/routes/',
				'Shared components in src/lib/components/',
				'Reactive stores as .svelte.ts files using class + $state',
			],
			test_framework: 'vitest + @testing-library/svelte',
			test_patterns: [
				'Use render() and screen from @testing-library/svelte',
				'Mock modules with vi.mock()',
			],
		},
	},
	{
		id: 'fastapi-python',
		name: 'FastAPI + Python',
		description: 'FastAPI with SQLAlchemy async ORM and Pydantic v2',
		context: {
			language: 'Python 3.12+',
			framework: 'FastAPI',
			conventions: [
				'Async/await throughout — all DB operations are async',
				'Pydantic v2 models for request/response validation',
				'Repository pattern for database access',
			],
			patterns: [
				'SQLAlchemy 2.0 async ORM with mapped_column',
				'Dependency injection via FastAPI Depends()',
				'Routers in app/routers/, models in app/models/',
			],
			test_framework: 'pytest + pytest-asyncio',
			test_patterns: [
				'Async test functions with @pytest.mark.asyncio',
				'In-memory SQLite for DB tests via fixtures',
				'FakeProvider pattern for mocking LLM calls',
			],
		},
	},
	{
		id: 'nextjs-react',
		name: 'Next.js + React',
		description: 'Next.js 14+ App Router with React and TypeScript',
		context: {
			language: 'TypeScript',
			framework: 'Next.js 14+ (App Router)',
			conventions: [
				'Use Server Components by default, "use client" only when needed',
				'Colocate page components with their route segments',
				'Use React Server Actions for form mutations',
			],
			patterns: [
				'App Router with layout.tsx / page.tsx / loading.tsx',
				'Server Components for data fetching, Client Components for interactivity',
				'Shared components in src/components/',
			],
			test_framework: 'Jest + React Testing Library',
			test_patterns: [
				'Use render() and screen from @testing-library/react',
				'Mock next/navigation hooks in tests',
			],
		},
	},
	{
		id: 'django-python',
		name: 'Django + Python',
		description: 'Django with Django REST Framework',
		context: {
			language: 'Python 3.10+',
			framework: 'Django + Django REST Framework',
			conventions: [
				'Class-based views with DRF ViewSets and Serializers',
				'Django ORM models with migrations',
				'URL routing via urlpatterns in urls.py',
			],
			patterns: [
				'Apps in separate directories with models/views/serializers/urls',
				'Settings split into base/dev/prod modules',
				'Custom permissions and authentication classes',
			],
			test_framework: 'pytest-django',
			test_patterns: [
				'Use APIClient for endpoint tests',
				'Factory Boy for test data generation',
			],
		},
	},
	{
		id: 'express-node',
		name: 'Express + Node',
		description: 'Express.js with TypeScript and Prisma',
		context: {
			language: 'TypeScript',
			framework: 'Express.js',
			conventions: [
				'Middleware chain for auth, validation, error handling',
				'Controller/Service/Repository layered architecture',
				'Environment config via dotenv',
			],
			patterns: [
				'Route handlers in src/routes/',
				'Prisma ORM for database access',
				'Zod schemas for request validation',
			],
			test_framework: 'Jest + Supertest',
			test_patterns: [
				'Use supertest for HTTP endpoint testing',
				'Mock Prisma client in unit tests',
			],
		},
	},
	{
		id: 'rails-ruby',
		name: 'Rails + Ruby',
		description: 'Ruby on Rails with standard conventions',
		context: {
			language: 'Ruby 3.2+',
			framework: 'Ruby on Rails 7',
			conventions: [
				'Convention over configuration',
				'RESTful resource routing',
				'ActiveRecord for ORM with migrations',
			],
			patterns: [
				'MVC: app/models, app/controllers, app/views',
				'Concerns for shared model/controller logic',
				'Service objects in app/services/ for complex business logic',
			],
			test_framework: 'RSpec',
			test_patterns: [
				'Request specs for controller testing',
				'FactoryBot for test data',
			],
		},
	},
	{
		id: 'spring-java',
		name: 'Spring Boot + Java',
		description: 'Spring Boot with JPA and Spring Security',
		context: {
			language: 'Java 17+',
			framework: 'Spring Boot 3',
			conventions: [
				'Constructor injection for dependencies',
				'JPA entities with Spring Data repositories',
				'@RestController for REST endpoints',
			],
			patterns: [
				'Layered: controller → service → repository',
				'DTOs for API request/response mapping',
				'Spring Security filter chain for auth',
			],
			test_framework: 'JUnit 5 + Spring Boot Test',
			test_patterns: [
				'@SpringBootTest for integration tests',
				'@WebMvcTest for controller unit tests with MockMvc',
			],
		},
	},
	{
		id: 'go-chi',
		name: 'Go + Chi/Gin',
		description: 'Go with Chi or Gin HTTP router',
		context: {
			language: 'Go 1.22+',
			framework: 'Chi / Gin HTTP router',
			conventions: [
				'Standard project layout: cmd/, internal/, pkg/',
				'Interfaces for dependency injection and testing',
				'Context propagation for request-scoped values',
			],
			patterns: [
				'Handler functions with middleware chains',
				'Repository interfaces with concrete implementations',
				'Struct embedding for composition over inheritance',
			],
			test_framework: 'Go testing + testify',
			test_patterns: [
				'Table-driven tests with t.Run()',
				'httptest.NewRecorder for handler tests',
			],
		},
	},
];
