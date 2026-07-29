import {
  Children,
  createContext,
  isValidElement,
  ReactNode,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

type NavigateOptions = { replace?: boolean; state?: unknown };
type NavigateFunction = (to: string, options?: NavigateOptions) => void;
type RouterContextValue = {
  pathname: string;
  navigate: NavigateFunction;
};
type RouteProps = {
  path?: string;
  index?: boolean;
  element?: ReactNode;
  children?: ReactNode;
};
type RouteMatch = {
  elements: ReactNode[];
  params: Record<string, string>;
};

const RouterContext = createContext<RouterContextValue | null>(null);
const OutletContext = createContext<ReactNode>(null);
const ParamsContext = createContext<Record<string, string>>({});

function currentPathname() {
  return window.location.pathname || '/';
}

function normalizePath(path: string) {
  const normalized = `/${path}`.replace(/\/+/g, '/').replace(/\/$/, '');
  return normalized || '/';
}

function joinPath(parent: string, child?: string) {
  if (!child) return normalizePath(parent);
  return child.startsWith('/') ? normalizePath(child) : normalizePath(`${parent}/${child}`);
}

function matchPath(pattern: string, pathname: string) {
  const expected = normalizePath(pattern).split('/').filter(Boolean);
  const actual = normalizePath(pathname).split('/').filter(Boolean);
  if (expected.length !== actual.length) return null;

  const params: Record<string, string> = {};
  for (let index = 0; index < expected.length; index += 1) {
    const segment = expected[index];
    if (segment.startsWith(':')) {
      try {
        params[segment.slice(1)] = decodeURIComponent(actual[index]);
      } catch {
        return null;
      }
    } else if (segment !== actual[index]) {
      return null;
    }
  }
  return params;
}

function findMatch(
  routes: ReactNode,
  pathname: string,
  parentPath = '/',
  parents: ReactNode[] = [],
): RouteMatch | null {
  for (const child of Children.toArray(routes)) {
    if (!isValidElement<RouteProps>(child) || child.type !== Route) continue;

    const props = child.props;
    const fullPath = props.index ? normalizePath(parentPath) : joinPath(parentPath, props.path);
    const elements = props.element == null ? parents : [...parents, props.element];

    if (props.children) {
      const nested = findMatch(props.children, pathname, fullPath, elements);
      if (nested) return nested;
    }

    if (!props.children || props.index) {
      const params = matchPath(fullPath, pathname);
      if (params) return { elements, params };
    }
  }
  return null;
}

function renderMatch(match: RouteMatch) {
  let rendered: ReactNode = null;
  for (let index = match.elements.length - 1; index >= 0; index -= 1) {
    rendered = (
      <OutletContext.Provider value={rendered}>
        {match.elements[index]}
      </OutletContext.Provider>
    );
  }
  return <ParamsContext.Provider value={match.params}>{rendered}</ParamsContext.Provider>;
}

export function BrowserRouter({ children }: { children: ReactNode }) {
  const [pathname, setPathname] = useState(currentPathname);

  useEffect(() => {
    const handlePopState = () => setPathname(currentPathname());
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const navigate = useMemo<NavigateFunction>(() => (to, options = {}) => {
    const target = new URL(to, window.location.origin);
    const next = `${target.pathname}${target.search}${target.hash}`;
    if (options.replace) window.history.replaceState(options.state ?? null, '', next);
    else window.history.pushState(options.state ?? null, '', next);
    setPathname(target.pathname);
    window.scrollTo({ top: 0, behavior: 'instant' });
  }, []);

  return (
    <RouterContext.Provider value={{ pathname, navigate }}>
      {children}
    </RouterContext.Provider>
  );
}

export function Route(_props: RouteProps) {
  return null;
}

export function Routes({ children }: { children: ReactNode }) {
  const { pathname } = useRouter();
  const match = findMatch(children, pathname);
  return match ? renderMatch(match) : null;
}

export function Outlet() {
  return <>{useContext(OutletContext)}</>;
}

export function Navigate({ to, replace = false }: { to: string; replace?: boolean }) {
  const navigate = useNavigate();
  useEffect(() => navigate(to, { replace }), [navigate, replace, to]);
  return null;
}

export function useNavigate() {
  return useRouter().navigate;
}

export function useLocation() {
  const { pathname } = useRouter();
  return { pathname, search: window.location.search, hash: window.location.hash };
}

export function useParams<T extends Record<string, string | undefined> = Record<string, string>>() {
  return useContext(ParamsContext) as T;
}

function useRouter() {
  const value = useContext(RouterContext);
  if (!value) throw new Error('Router components must be rendered inside BrowserRouter.');
  return value;
}

type LinkProps = Omit<React.AnchorHTMLAttributes<HTMLAnchorElement>, 'href'> & {
  to: string;
};

export function Link({ to, onClick, ...props }: LinkProps) {
  const navigate = useNavigate();
  return (
    <a
      href={to}
      onClick={(event) => {
        onClick?.(event);
        if (
          event.defaultPrevented
          || event.button !== 0
          || event.metaKey
          || event.ctrlKey
          || event.shiftKey
          || event.altKey
          || props.target === '_blank'
        ) return;
        event.preventDefault();
        navigate(to);
      }}
      {...props}
    />
  );
}

type NavLinkState = { isActive: boolean };
type NavLinkProps = Omit<LinkProps, 'className' | 'children'> & {
  end?: boolean;
  className?: string | ((state: NavLinkState) => string);
  children?: ReactNode | ((state: NavLinkState) => ReactNode);
};

export function NavLink({ to, end = false, className, children, ...props }: NavLinkProps) {
  const { pathname } = useLocation();
  const normalizedTo = normalizePath(to);
  const normalizedPath = normalizePath(pathname);
  const isActive = normalizedPath === normalizedTo
    || (!end && normalizedTo !== '/' && normalizedPath.startsWith(`${normalizedTo}/`));
  const state = { isActive };
  return (
    <Link
      to={to}
      className={typeof className === 'function' ? className(state) : className}
      {...props}
    >
      {typeof children === 'function' ? children(state) : children}
    </Link>
  );
}
