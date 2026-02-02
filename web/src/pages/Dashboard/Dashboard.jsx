import {
  DEFAULT_USER_ID,
  DEFAULT_WATCHLIST_NAMES,
  DEFAULT_WATCHLIST_SYMBOLS,
  INDEX_SYMBOLS,
  addPortfolioHolding,
  addWatchlistItem,
  deletePortfolioHolding,
  deleteWatchlistItem,
  fallbackIndex,
  getIndices,
  getPortfolio,
  getStockPrices,
  listWatchlists,
  listWatchlistItems,
  normalizeIndexSymbol,
  updatePortfolioHolding,
} from './utils/api';
import { useCallback, useEffect, useState } from 'react';
import { useToast } from '@/components/ui/use-toast';
import DashboardHeader from './components/DashboardHeader';
import ConfirmDialog from './components/ConfirmDialog';
import IndexMovementCard from './components/IndexMovementCard';
import PopularCard from './components/PopularCard';
import TopNewsCard from './components/TopNewsCard';
import TopResearchCard from './components/TopResearchCard';
import ChatInputCard from './components/ChatInputCard';
import WatchlistCard from './components/WatchlistCard';
import AddWatchlistItemDialog from './components/AddWatchlistItemDialog';
import PortfolioCard from './components/PortfolioCard';
import './Dashboard.css';

const POPULAR_ITEMS = [
    { title: 'Comparison Report', description: 'A comprehensive analysis comparing industries.', duration: '20-30min', isHighlighted: true },
    { title: 'Comparison Report', description: 'A comprehensive analysis comparing industries.', duration: '20-30min', isHighlighted: false },
    { title: 'Comparison Report', description: 'A comprehensive analysis comparing industries.', duration: '20-30min', isHighlighted: false },
    { title: 'Comparison Report', description: 'A comprehensive analysis comparing industries.', duration: '20-30min', isHighlighted: false },
  ];

const NEWS_ITEMS = [
    { title: 'Federal Reserve Signals Potential Rate Cuts Amid Economic Uncertainty', time: '5 min ago', isHot: true },
    { title: 'Tech Stocks Rally as AI Companies Report Record Quarterly Earnings', time: '12 min ago', isHot: false },
    { title: 'Oil Prices Surge Following OPEC Production Cut Announcement', time: '18 min ago', isHot: true },
    { title: 'Cryptocurrency Market Volatility Increases as Regulatory News Emerges', time: '25 min ago', isHot: false },
    { title: 'Global Supply Chain Disruptions Impact Manufacturing Sector Performance', time: '1 hr ago', isHot: true },
    { title: 'Housing Market Shows Signs of Cooling as Mortgage Rates Climb', time: '2 hrs ago', isHot: false },
    { title: 'European Central Bank Maintains Current Interest Rate Policy', time: '3 hrs ago', isHot: false },
    { title: 'Renewable Energy Investments Reach All-Time High in Q4', time: '5 hrs ago', isHot: true },
  ];

const RESEARCH_ITEMS = [
    { title: 'Retail Sales Slump Takes Toll on Market, Stocks Dip', time: '10 min ago' },
    { title: 'Retail Sales Slump Takes Toll on Market, Stocks Dip', time: '10 min ago' },
    { title: 'Retail Sales Slump Takes Toll on Market, Stocks Dip', time: '10 min ago' },
    { title: 'Retail Sales Slump Takes Toll on Market, Stocks Dip', time: '10 min ago' },
  ];

function Dashboard() {
  const { toast } = useToast();
  
  const [indices, setIndices] = useState(() =>
    INDEX_SYMBOLS.map((s) => fallbackIndex(normalizeIndexSymbol(s)))
  );
  const [indicesLoading, setIndicesLoading] = useState(true);

  const fetchIndices = useCallback(async () => {
    setIndicesLoading(true);
    try {
      console.log('[Dashboard] Fetching indices - Request params:', {
        symbols: INDEX_SYMBOLS,
        timestamp: new Date().toISOString(),
      });
      
      // API doesn't require from/to params - just call with symbols
      const { indices: next } = await getIndices(INDEX_SYMBOLS);
      
      console.log('[Dashboard] Received indices response:', {
        indices: next,
        count: next?.length,
        sample: next?.[0],
        timestamp: new Date().toISOString(),
      });
      
      setIndices(next);
    } catch (error) {
      console.error('[Dashboard] Error fetching indices:', {
        error,
        message: error?.message,
        stack: error?.stack,
        timestamp: new Date().toISOString(),
      });
      setIndices(INDEX_SYMBOLS.map((s) => fallbackIndex(normalizeIndexSymbol(s))));
    } finally {
      setIndicesLoading(false);
    }
  }, []);

  useEffect(() => {
    // Fetch immediately on mount
    fetchIndices();
    
    // Set up interval to fetch every minute (60000ms)
    const intervalId = setInterval(() => {
      console.log('[Dashboard] Auto-refreshing Index Movement data (1 minute interval)');
      fetchIndices();
    }, 60000); // 60 seconds = 1 minute
    
    // Cleanup interval on unmount
    return () => {
      clearInterval(intervalId);
    };
  }, [fetchIndices]);

  const [watchlistRows, setWatchlistRows] = useState([]);
  const [watchlistLoading, setWatchlistLoading] = useState(true);
  const [watchlistModalOpen, setWatchlistModalOpen] = useState(false);
  const [currentWatchlistId, setCurrentWatchlistId] = useState(null);
  
  /**
   * Fetches watchlist data by:
   * 1. Getting all watchlists for the user
   * 2. Using the first watchlist's ID to fetch its items
   * 3. Getting stock prices for those symbols
   * 4. Combining the data for display
   */
  const fetchWatchlist = useCallback(async () => {
    setWatchlistLoading(true);
    try {
      // Step 1: Get all watchlists for the user
      const { watchlists } = await listWatchlists(DEFAULT_USER_ID);
      
      // Step 2: Get the first watchlist's ID (or use 'default' if no watchlists exist)
      const firstWatchlist = watchlists?.[0];
      const watchlistId = firstWatchlist?.watchlist_id || 'default';
      
      // Store the watchlist ID for use in add/delete operations
      setCurrentWatchlistId(watchlistId);
      
      // Step 3: Fetch items for the watchlist
      const { items } = await listWatchlistItems(watchlistId, DEFAULT_USER_ID);
      
      // Step 4: Extract symbols from items (empty array if no items)
      const symbols = items?.length ? items.map((i) => i.symbol) : [];
      
      // Step 5: Get stock prices for the symbols (only if there are symbols)
      const prices = symbols.length > 0 ? await getStockPrices(symbols) : [];
      const bySym = Object.fromEntries((prices || []).map((p) => [p.symbol, p]));
      
      // Step 6: Combine watchlist items with price data
      // If no items exist, set empty array
      const rows = items?.length
        ? items.map((i) => {
            const sym = String(i.symbol || '').trim().toUpperCase();
            const p = bySym[sym] || {};
            return {
              item_id: i.item_id,
              symbol: sym,
              price: p.price ?? 0,
              change: p.change ?? 0,
              changePercent: p.changePercent ?? 0,
              isPositive: p.isPositive ?? true,
            };
          })
        : [];
      setWatchlistRows(rows);
    } catch {
      // If any step fails, set empty rows (no fallback to default symbols)
      setWatchlistRows([]);
    } finally {
      setWatchlistLoading(false);
    }
  }, []);

  useEffect(() => {
    // Fetch immediately on mount
    fetchWatchlist();
    
    // Set up interval to fetch every minute (60000ms)
    const intervalId = setInterval(() => {
      console.log('[Dashboard] Auto-refreshing Watchlist data (1 minute interval)');
      fetchWatchlist();
    }, 60000); // 60 seconds = 1 minute
    
    // Cleanup interval on unmount
    return () => {
      clearInterval(intervalId);
    };
  }, [fetchWatchlist]);

  const [deleteConfirm, setDeleteConfirm] = useState({
    open: false,
    title: '',
    message: '',
    onConfirm: null,
  });

  /**
   * Adds a stock to the current watchlist with full details
   * Uses the watchlist ID from the most recent fetch
   * @param {Object} itemData - Stock item data: { symbol, instrument_type, exchange, name, notes, alert_settings }
   * @param {string} watchlistId - The watchlist ID
   * @param {string} userId - The user ID
   */
  const handleAddWatchlist = useCallback(async (itemData, watchlistId, userId) => {
    try {
      // Ensure we have a watchlist ID
      let targetWatchlistId = watchlistId || currentWatchlistId;
      if (!targetWatchlistId) {
        const { watchlists } = await listWatchlists(DEFAULT_USER_ID);
        targetWatchlistId = watchlists?.[0]?.watchlist_id || 'default';
        setCurrentWatchlistId(targetWatchlistId);
      }
      
      await addWatchlistItem(itemData, targetWatchlistId, userId || DEFAULT_USER_ID);
      setWatchlistModalOpen(false);
      fetchWatchlist();
      
      toast({
        title: 'Stock added',
        description: `${itemData.symbol} has been added to your watchlist.`,
      });
    } catch (e) {
      console.error('Add watchlist item failed:', e?.response?.status, e?.response?.data, e?.message);
      
      const status = e?.response?.status;
      const msg = e?.response?.data?.detail || e?.response?.data?.message || '';
      
      if (status === 409 || msg.toLowerCase().includes('already exists')) {
        toast({
          variant: 'destructive',
          title: 'Already in watchlist',
          description: `${itemData.symbol} is already in your watchlist.`,
        });
      } else {
        toast({
          variant: 'destructive',
          title: 'Cannot add stock',
          description: msg || 'Failed to add to watchlist. Please try again.',
        });
      }
    }
  }, [currentWatchlistId, fetchWatchlist, toast]);

  /**
   * Deletes a watchlist item by ID
   * Uses the watchlist ID from the most recent fetch
   */
  const handleDeleteWatchlistItem = useCallback(
    async (itemId) => {
      try {
        // Get current watchlist ID (or fetch it if not available)
        let watchlistId = currentWatchlistId;
        if (!watchlistId) {
          const { watchlists } = await listWatchlists(DEFAULT_USER_ID);
          watchlistId = watchlists?.[0]?.watchlist_id || 'default';
          setCurrentWatchlistId(watchlistId);
        }
        
        await deleteWatchlistItem(itemId, watchlistId, DEFAULT_USER_ID);
        fetchWatchlist();
      } catch (e) {
        console.error('Delete watchlist item failed:', e?.response?.status, e?.response?.data, e?.message);
      }
    },
    [currentWatchlistId, fetchWatchlist]
  );

  const [portfolioRows, setPortfolioRows] = useState([]);
  const [portfolioLoading, setPortfolioLoading] = useState(true);
  const [portfolioHasRealHoldings, setPortfolioHasRealHoldings] = useState(false);
  const [portfolioModalOpen, setPortfolioModalOpen] = useState(false);
  const [portfolioForm, setPortfolioForm] = useState({
    symbol: '',
    quantity: '',
    averageCost: '',
    accountName: '',
    notes: '',
  });

  const fetchPortfolio = useCallback(async () => {
    setPortfolioLoading(true);
    try {
      const { holdings } = await getPortfolio(DEFAULT_USER_ID);
      const symbols = holdings?.length
        ? holdings.map((h) => String(h.symbol || '').trim().toUpperCase())
        : DEFAULT_WATCHLIST_SYMBOLS;
      const prices = await getStockPrices(symbols);
      const bySym = Object.fromEntries((prices || []).map((p) => [p.symbol, p]));
      if (holdings?.length) {
        setPortfolioHasRealHoldings(true);
        const rows = holdings.map((h) => {
          const sym = String(h.symbol || '').trim().toUpperCase();
          const p = bySym[sym] || {};
          const q = Number(h.quantity);
          const ac = h.average_cost != null ? Number(h.average_cost) : null;
          const price = p.price ?? 0;
          const marketValue = q * price;
          const plPct = ac != null && ac > 0 ? ((price - ac) / ac) * 100 : null;
          return {
            holding_id: h.holding_id,
            symbol: sym,
            quantity: q,
            average_cost: ac,
            notes: h.notes ?? '',
            price,
            marketValue,
            unrealizedPlPercent: plPct,
            isPositive: plPct == null ? true : plPct >= 0,
          };
        });
        setPortfolioRows(rows);
      } else {
        setPortfolioHasRealHoldings(false);
        const rows = DEFAULT_WATCHLIST_SYMBOLS.map((s) => {
          const p = bySym[s] || {};
          return {
            symbol: s,
            name: DEFAULT_WATCHLIST_NAMES[s] || s,
            price: p.price ?? 0,
            quantity: null,
            marketValue: null,
            unrealizedPlPercent: null,
            isPositive: p.isPositive ?? true,
          };
        });
        setPortfolioRows(rows);
      }
    } catch {
      setPortfolioHasRealHoldings(false);
      const prices = await getStockPrices(DEFAULT_WATCHLIST_SYMBOLS);
      const bySym = Object.fromEntries((prices || []).map((p) => [p.symbol, p]));
      setPortfolioRows(
        DEFAULT_WATCHLIST_SYMBOLS.map((s) => {
          const p = bySym[s] || {};
          return {
            symbol: s,
            price: p.price ?? 0,
            quantity: null,
            marketValue: null,
            unrealizedPlPercent: null,
            isPositive: p.isPositive ?? true,
          };
        })
      );
    } finally {
      setPortfolioLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPortfolio();
  }, [fetchPortfolio]);

  const handleDeletePortfolioItem = useCallback(
    (holdingId) => {
      setDeleteConfirm({
        open: true,
        title: 'Remove holding',
        message: 'Remove this holding from your portfolio?',
        onConfirm: async () => {
          try {
            await deletePortfolioHolding(holdingId, DEFAULT_USER_ID);
            fetchPortfolio();
          } catch (e) {
            console.error('Delete portfolio holding failed:', e?.response?.status, e?.response?.data, e?.message);
          }
        },
      });
    },
    [fetchPortfolio]
  );

  const handleAddPortfolio = useCallback(async () => {
    const sym = String(portfolioForm.symbol || '').trim().toUpperCase();
    const q = Number(portfolioForm.quantity);
    const ac = Number(portfolioForm.averageCost);
    if (!sym || !Number.isFinite(q) || q <= 0 || !Number.isFinite(ac) || ac <= 0) return;
    const payload = {
      symbol: sym,
      instrument_type: 'stock',
      quantity: q,
      average_cost: ac,
      currency: 'USD',
      exchange: 'NASDAQ',
      account_name: portfolioForm.accountName?.trim() || undefined,
      notes: portfolioForm.notes?.trim() || undefined,
      first_purchased_at: new Date().toISOString(),
    };
    try {
      await addPortfolioHolding(payload, DEFAULT_USER_ID);
      setPortfolioForm({ symbol: '', quantity: '', averageCost: '', accountName: '', notes: '' });
      setPortfolioModalOpen(false);
      fetchPortfolio();
    } catch (e) {
      console.error('Add portfolio holding failed:', e?.response?.status, e?.response?.data, e?.message);
      
      const msg = e?.response?.data?.detail || e?.response?.data?.message || '';
      
      if (msg.includes('数字字段溢出') || msg.includes('NumericValueOutOfRange')) {
        toast({
          variant: 'destructive',
          title: 'Holding amount too large',
          description: 'The total position value exceeds system limits. Try reducing quantity or price.',
        });
      } else {
        toast({
          variant: 'destructive',
          title: 'Cannot add holding',
          description: 'Failed to add holding. Please try again.',
        });
      }
    }
  }, [portfolioForm, fetchPortfolio]);

  const [portfolioEditRow, setPortfolioEditRow] = useState(null);
  const [portfolioEditForm, setPortfolioEditForm] = useState({ quantity: '', averageCost: '', notes: '' });

  const openPortfolioEdit = useCallback((row) => {
    setPortfolioEditRow(row);
    setPortfolioEditForm({
      quantity: row.quantity != null ? String(row.quantity) : '',
      averageCost: row.average_cost != null ? String(row.average_cost) : '',
      notes: row.notes ?? '',
    });
  }, []);

  const handleUpdatePortfolio = useCallback(async () => {
    if (!portfolioEditRow?.holding_id) return;
    const q = Number(portfolioEditForm.quantity);
    const ac = Number(portfolioEditForm.averageCost);
    if (!Number.isFinite(q) || q <= 0 || !Number.isFinite(ac) || ac <= 0) return;
    try {
      await updatePortfolioHolding(
        portfolioEditRow.holding_id,
        {
          quantity: q,
          average_cost: ac,
          notes: portfolioEditForm.notes.trim() || undefined,
        },
        DEFAULT_USER_ID
      );
      setPortfolioEditRow(null);
      fetchPortfolio();
    } catch (e) {
      console.error('Update portfolio holding failed:', e?.response?.status, e?.response?.data, e?.message);
      
      const msg = e?.response?.data?.detail || e?.response?.data?.message || '';
      
      if (msg.includes('NumericValueOutOfRange')) {
        toast({
          variant: 'destructive',
          title: 'Holding amount too large',
          description: 'The total position value exceeds system limits. Try reducing quantity or price.',
        });
      } else {
        toast({
          variant: 'destructive',
          title: 'Update failed',
          description: 'Something went wrong while saving your portfolio.',
        });
      }
    }
  }, [portfolioEditRow, portfolioEditForm, fetchPortfolio]);

  const runDeleteConfirm = useCallback(async () => {
    if (deleteConfirm.onConfirm) await deleteConfirm.onConfirm();
    setDeleteConfirm((p) => ({ ...p, open: false }));
  }, [deleteConfirm.onConfirm]);

  return (
    <div className="dashboard-container min-h-screen">
      <ConfirmDialog
        open={deleteConfirm.open}
        title={deleteConfirm.title}
        message={deleteConfirm.message}
        confirmLabel="Delete"
        onConfirm={runDeleteConfirm}
        onOpenChange={(open) => !open && setDeleteConfirm((p) => ({ ...p, open: false }))}
            />

      <DashboardHeader />

      <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
        <div className="w-full flex-1 min-h-0 flex justify-center">
          <div className="w-full h-full min-h-0 max-w-[1400px] px-6 py-4 flex flex-col">
            <div className="grid grid-cols-[1fr_360px] gap-4 flex-1 min-h-0 h-full">
              <div className="w-full flex flex-col gap-4 h-full min-h-0 overflow-hidden">
                <IndexMovementCard indices={indices} loading={indicesLoading} />
                <PopularCard items={POPULAR_ITEMS} />
                <div className="w-full grid grid-cols-2 gap-4 flex-1 min-h-0 overflow-hidden">
                  <TopNewsCard items={NEWS_ITEMS} />
                  <TopResearchCard items={RESEARCH_ITEMS} />
                </div>
                <ChatInputCard />
              </div>

              <div className="w-full flex flex-col gap-4 h-full min-h-0 overflow-hidden">
                <WatchlistCard
                  rows={watchlistRows}
                  loading={watchlistLoading}
                  onHeaderAddClick={() => setWatchlistModalOpen(true)}
                  onDeleteItem={handleDeleteWatchlistItem}
                />
                <AddWatchlistItemDialog
                  open={watchlistModalOpen}
                  onClose={() => setWatchlistModalOpen(false)}
                  onAdd={handleAddWatchlist}
                  watchlistId={currentWatchlistId}
                  userId={DEFAULT_USER_ID}
                />
                <PortfolioCard
                  rows={portfolioRows}
                  loading={portfolioLoading}
                  hasRealHoldings={portfolioHasRealHoldings}
                  addModalOpen={portfolioModalOpen}
                  onAddModalClose={() => setPortfolioModalOpen(false)}
                  onHeaderAddClick={() => setPortfolioModalOpen(true)}
                  addForm={portfolioForm}
                  onAddFormChange={setPortfolioForm}
                  onAddSubmit={handleAddPortfolio}
                  editRow={portfolioEditRow}
                  editForm={portfolioEditForm}
                  onEditFormChange={setPortfolioEditForm}
                  onEditSubmit={handleUpdatePortfolio}
                  onEditClose={() => setPortfolioEditRow(null)}
                  onDeleteItem={handleDeletePortfolioItem}
                  onEditItem={openPortfolioEdit}
                />
                    </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
