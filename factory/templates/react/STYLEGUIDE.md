# Style Guide

This document defines the coding standards for this project. All contributors (human and AI) must follow these rules.

## TypeScript

### Formatting
- **Formatter**: Prettier
- **Line length**: 100 characters
- **Indentation**: 2 spaces
- **Semicolons**: always
- **Trailing commas**: always in multi-line (`"trailingComma": "all"`)
- **Quotes**: double quotes for JSX attributes, single quotes for imports/strings

### Naming
- **Variables/functions**: `camelCase`
- **Components**: `PascalCase` (both filename and export)
- **Types/Interfaces**: `PascalCase`, no `I` prefix (`UserProps` not `IUserProps`)
- **Constants**: `UPPER_SNAKE_CASE` for true constants, `camelCase` for derived values
- **Event handlers**: `handle` prefix (`handleClick`, `handleSubmit`)
- **Boolean props**: `is`/`has`/`should` prefix (`isLoading`, `hasError`)

### Components
- **Functional components only**: no class components
- **Named exports**: no default exports (`export function App()` not `export default App`)
- **Props destructured in params**: `function Card({ title, body }: CardProps)` not `function Card(props: CardProps)`
- **One component per file**: exception for small helper components used only by the parent
- **Max component length**: ~100 lines. Extract sub-components if longer

```tsx
interface WeatherCardProps {
  city: string;
  temperature: number;
  description: string;
  isLoading: boolean;
}

export function WeatherCard({
  city,
  temperature,
  description,
  isLoading,
}: WeatherCardProps): React.ReactElement {
  if (isLoading) {
    return <Skeleton />;
  }

  return (
    <div className="rounded-lg bg-white p-4 shadow">
      <h2 className="text-lg font-bold">{city}</h2>
      <p className="text-3xl">{temperature}°</p>
      <p className="text-gray-500">{description}</p>
    </div>
  );
}
```

### Types
- **Interfaces for component props**: `interface ButtonProps { ... }`
- **Types for unions/intersections**: `type Status = "idle" | "loading" | "error";`
- **No `any`**: use `unknown` if the type is truly unknown, then narrow it
- **Return types on all functions**: explicit `React.ReactElement` for components
- **Generic types** when a function works with multiple types

### State Management
- **useState** for local component state
- **useReducer** for complex state with multiple actions
- **Props drilling max 2 levels**: beyond that, use context or state management
- **Derive state** instead of syncing: compute values from existing state, don't duplicate

### Hooks
- **Custom hooks** for reusable logic: `useWeather()`, `useDebounce()`
- **Prefix with `use`**: always
- **No side effects in render**: use `useEffect` for side effects
- **Cleanup effects**: always return a cleanup function from `useEffect` when subscribing

### Styling
- **Tailwind utility classes**: no inline styles, no CSS modules
- **Responsive mobile-first**: `text-sm md:text-base lg:text-lg`
- **Semantic class grouping**: layout → spacing → typography → colors → effects
- **Extract repeated patterns** into components, not utility classes

### Error Handling
- **Error boundaries** for component tree protection
- **Loading/error/empty states**: every async component handles all three
- **User-facing error messages**: never show raw error objects or stack traces

## Testing

- **Test files co-located**: `Component.tsx` + `Component.test.tsx` in same directory, or in `__tests__/`
- **Testing Library**: test behavior, not implementation (`getByRole`, `getByText`)
- **No snapshot tests**: they break on every change and provide no value
- **Test user interactions**: click, type, submit — not internal state
- **Mock API calls**: never make real HTTP requests in tests
- **Descriptive test names**: `it("shows error message when city not found")`

## Git

- **Commit messages**: imperative mood ("Add feature" not "Added feature")
- **One logical change per commit**
- **No generated files committed**: no `node_modules`, no `dist/`, no `.env`
