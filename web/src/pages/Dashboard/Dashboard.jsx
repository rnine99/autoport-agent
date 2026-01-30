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
  getWatchlistItems,
  normalizeIndexSymbol,
} from '@/api';
import { AlignEndHorizontal, ChevronDown, Clock, Globe, Menu, Plus, Send, Sparkles, Trash2, X, Zap } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { Input } from '../../components/ui/input';
import { ScrollArea } from '../../components/ui/scroll-area';
import DashboardHeader from './components/DashboardHeader';
import './Dashboard.css';

function Dashboard() {
  const [indices, setIndices] = useState(() =>
    INDEX_SYMBOLS.map((s) => fallbackIndex(normalizeIndexSymbol(s)))
  );
  const [indicesLoading, setIndicesLoading] = useState(true);

  const fetchIndices = useCallback(async () => {
    setIndicesLoading(true);
    try {
      const { indices: next } = await getIndices(INDEX_SYMBOLS);
      setIndices(next);
    } catch {
      setIndices(INDEX_SYMBOLS.map((s) => fallbackIndex(normalizeIndexSymbol(s))));
    } finally {
      setIndicesLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchIndices();
  }, [fetchIndices]);

  const [watchlistRows, setWatchlistRows] = useState([]);
  const [watchlistLoading, setWatchlistLoading] = useState(true);
  const [watchlistModalOpen, setWatchlistModalOpen] = useState(false);
  const [addSymbol, setAddSymbol] = useState('');

  const fetchWatchlist = useCallback(async () => {
    setWatchlistLoading(true);
    try {
      const { items } = await getWatchlistItems(DEFAULT_USER_ID);
      const symbols = items?.length
        ? items.map((i) => i.symbol)
        : DEFAULT_WATCHLIST_SYMBOLS;
      const prices = await getStockPrices(symbols);
      const bySym = Object.fromEntries((prices || []).map((p) => [p.symbol, p]));
      const rows = items?.length
        ? items.map((i) => {
            const sym = String(i.symbol || '').trim().toUpperCase();
            const p = bySym[sym] || {};
            return {
              item_id: i.item_id,
              symbol: sym,
              name: i.name || sym,
              price: p.price ?? 0,
              change: p.change ?? 0,
              changePercent: p.changePercent ?? 0,
              isPositive: p.isPositive ?? true,
            };
          })
        : DEFAULT_WATCHLIST_SYMBOLS.map((s) => {
            const p = bySym[s] || {};
            return {
              symbol: s,
              name: DEFAULT_WATCHLIST_NAMES[s] || s,
              price: p.price ?? 0,
              change: p.change ?? 0,
              changePercent: p.changePercent ?? 0,
              isPositive: p.isPositive ?? true,
            };
          });
      setWatchlistRows(rows);
    } catch {
      const prices = await getStockPrices(DEFAULT_WATCHLIST_SYMBOLS);
      const bySym = Object.fromEntries((prices || []).map((p) => [p.symbol, p]));
      setWatchlistRows(
        DEFAULT_WATCHLIST_SYMBOLS.map((s) => {
          const p = bySym[s] || {};
          return {
            symbol: s,
            name: DEFAULT_WATCHLIST_NAMES[s] || s,
            price: p.price ?? 0,
            change: p.change ?? 0,
            changePercent: p.changePercent ?? 0,
            isPositive: p.isPositive ?? true,
          };
        })
      );
    } finally {
      setWatchlistLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWatchlist();
  }, [fetchWatchlist]);

  const [deleteConfirm, setDeleteConfirm] = useState({
    open: false,
    title: '',
    message: '',
    onConfirm: null,
  });

  const handleAddWatchlist = useCallback(async () => {
    const sym = addSymbol.trim().toUpperCase();
    if (!sym) return;
    try {
      await addWatchlistItem(sym, DEFAULT_USER_ID);
      setAddSymbol('');
      setWatchlistModalOpen(false);
      fetchWatchlist();
    } catch (e) {
      console.error('Add watchlist item failed:', e?.response?.status, e?.response?.data, e?.message);
    }
  }, [addSymbol, fetchWatchlist]);

  const handleDeleteWatchlistItem = useCallback(
    (itemId) => {
      setDeleteConfirm({
        open: true,
        title: 'Remove from watchlist',
        message: 'Remove this item?',
        onConfirm: async () => {
          try {
            await deleteWatchlistItem(itemId, DEFAULT_USER_ID);
            fetchWatchlist();
          } catch (e) {
            console.error('Delete watchlist item failed:', e?.response?.status, e?.response?.data, e?.message);
          }
        },
      });
    },
    [fetchWatchlist]
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
            name: h.name || DEFAULT_WATCHLIST_NAMES[sym] || sym,
            symbol: sym,
            quantity: q,
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
            name: DEFAULT_WATCHLIST_NAMES[s] || s,
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
      name: DEFAULT_WATCHLIST_NAMES[sym] || undefined,
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
    }
  }, [portfolioForm, fetchPortfolio]);

  const popularItems = [
    { title: 'Comparison Report', description: 'A comprehensive analysis comparing industries.', duration: '20-30min', isHighlighted: true },
    { title: 'Comparison Report', description: 'A comprehensive analysis comparing industries.', duration: '20-30min', isHighlighted: false },
    { title: 'Comparison Report', description: 'A comprehensive analysis comparing industries.', duration: '20-30min', isHighlighted: false },
    { title: 'Comparison Report', description: 'A comprehensive analysis comparing industries.', duration: '20-30min', isHighlighted: false },
  ];

  const newsItems = [
    { title: 'Federal Reserve Signals Potential Rate Cuts Amid Economic Uncertainty', time: '5 min ago', isHot: true },
    { title: 'Tech Stocks Rally as AI Companies Report Record Quarterly Earnings', time: '12 min ago', isHot: false },
    { title: 'Oil Prices Surge Following OPEC Production Cut Announcement', time: '18 min ago', isHot: true },
    { title: 'Cryptocurrency Market Volatility Increases as Regulatory News Emerges', time: '25 min ago', isHot: false },
    { title: 'Global Supply Chain Disruptions Impact Manufacturing Sector Performance', time: '1 hr ago', isHot: true },
    { title: 'Housing Market Shows Signs of Cooling as Mortgage Rates Climb', time: '2 hrs ago', isHot: false },
    { title: 'European Central Bank Maintains Current Interest Rate Policy', time: '3 hrs ago', isHot: false },
    { title: 'Renewable Energy Investments Reach All-Time High in Q4', time: '5 hrs ago', isHot: true },
  ];

  const researchItems = [
    { title: 'Retail Sales Slump Takes Toll on Market, Stocks Dip', time: '10 min ago' },
    { title: 'Retail Sales Slump Takes Toll on Market, Stocks Dip', time: '10 min ago' },
    { title: 'Retail Sales Slump Takes Toll on Market, Stocks Dip', time: '10 min ago' },
    { title: 'Retail Sales Slump Takes Toll on Market, Stocks Dip', time: '10 min ago' },
  ];

  const isPortfolioReal = portfolioHasRealHoldings;

  const runDeleteConfirm = useCallback(async () => {
    if (deleteConfirm.onConfirm) await deleteConfirm.onConfirm();
    setDeleteConfirm((p) => ({ ...p, open: false }));
  }, [deleteConfirm.onConfirm]);

  return (
    <div className="dashboard-container min-h-screen" style={{ backgroundColor: '#1B1D25' }}>
      {/* Delete confirmation */}
      <Dialog open={deleteConfirm.open} onOpenChange={(open) => !open && setDeleteConfirm((p) => ({ ...p, open: false }))}>
        <DialogContent className="sm:max-w-sm bg-[#1B1D25] border-[#2a2d38] text-white">
          <DialogHeader>
            <DialogTitle style={{ color: '#FFFFFF' }}>{deleteConfirm.title}</DialogTitle>
            <p className="text-sm text-gray-400">{deleteConfirm.message}</p>
          </DialogHeader>
          <DialogFooter className="gap-2 pt-4">
            <button
              type="button"
              onClick={() => setDeleteConfirm((p) => ({ ...p, open: false }))}
              className="px-3 py-1.5 rounded text-sm border border-[#202020] hover:bg-white/10"
              style={{ color: '#FFFFFF' }}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={runDeleteConfirm}
              className="px-4 py-1.5 rounded text-sm font-medium hover:opacity-90"
              style={{ backgroundColor: '#6155F5', color: '#FFFFFF' }}
            >
              Delete
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Header */}
      <DashboardHeader />

      {/* Main Content Grid — 高度随屏幕，News/Research 伸缩 */}
      <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
        <div className="w-full flex-1 min-h-0 flex justify-center">
          <div className="w-full h-full min-h-0 max-w-[1400px] px-6 py-4 flex flex-col">
            <div className="grid grid-cols-[1fr_360px] gap-4 flex-1 min-h-0 h-full">
              {/* Left Column */}
              <div className="w-full flex flex-col gap-4 h-full min-h-0 overflow-hidden">
                {/* Index Movement */}
                <Card className="w-full fin-card flex-shrink-0" style={{ backgroundColor: 'transparent', border: 'none', boxShadow: 'none' }}>
              <div className="flex items-center gap-2.5 p-0">
                {/* Title Section */}
                <div className="flex flex-col gap-3 flex-shrink-0" style={{ width: '200px' }}>
                  <CardTitle className="text-base font-semibold" style={{ color: '#FFFFFF', letterSpacing: '0.15px', lineHeight: '24px' }}>Index Movement</CardTitle>
                  <p className="text-xs" style={{ color: '#FFFFFF', opacity: 0.65, letterSpacing: '0.4px', lineHeight: '16px' }}>Some summary words</p>
                </div>
                
                {/* Index Cards */}
                <div className="flex gap-2.5 flex-1 min-w-0">
                    {indicesLoading
                      ? Array.from({ length: 4 }).map((_, i) => (
                          <div
                            key={i}
                            className="flex-1 flex flex-col gap-2 p-4 rounded-lg min-w-0 animate-pulse"
                            style={{ backgroundColor: '#0A0A0A', border: '1px solid #202020' }}
                          >
                            <div className="h-4 rounded bg-white/10" style={{ width: '60%' }} />
                            <div className="h-4 rounded bg-white/10" style={{ width: '80%' }} />
                            <div className="h-4 rounded bg-white/10" style={{ width: '50%' }} />
                          </div>
                        ))
                      : indices.map((index, idx) => {
                          const pos = index.isPositive;
                          const ch = Number(index.change);
                          const pct = Number(index.changePercent);
                          const changeStr = (pos ? '+' : '') + ch.toFixed(2);
                          const pctStr = (pos ? '+' : '') + pct.toFixed(2) + '%';
                          return (
                            <div
                              key={index.symbol}
                              className="flex-1 flex flex-col gap-2 p-4 transition-all relative"
                              style={{ backgroundColor: '#0A0A0A', border: '1px solid #202020', borderRadius: '8px', minWidth: '0' }}
                            >
                              {idx > 0 && (
                                <div
                                  className="absolute left-0 top-1/2 transform -translate-y-1/2 -translate-x-1.25"
                                  style={{ width: '1px', height: '60px', backgroundColor: 'rgba(255, 255, 255, 0.1)' }}
                                />
                              )}
                              <div className="flex flex-col gap-2">
                                <p className="text-sm leading-tight truncate" style={{ color: '#FFFFFF', fontSize: '14px', lineHeight: '18px' }}>{index.name}</p>
                                <p className="text-sm tabular-nums leading-none" style={{ color: '#FFFFFF', opacity: 0.65, fontSize: '14px', lineHeight: '18px' }}>
                                  {Number(index.price).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                </p>
                                <div className="flex items-center gap-2 flex-wrap">
                                  <p className={`text-sm font-normal tabular-nums ${pos ? 'text-up' : 'text-down'}`} style={{ fontSize: '14px', lineHeight: '18px' }}>{changeStr}</p>
                                  <p className={`text-sm font-normal tabular-nums ${pos ? 'text-up' : 'text-down'}`} style={{ fontSize: '14px', lineHeight: '18px' }}>{pctStr}</p>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                </div>
              </div>
            </Card>

            {/* What's Popular */}
            <Card 
              className="flex-shrink-0"
              style={{ 
                background: 'linear-gradient(90deg, #6155F5 0%, #8F88EC 28.85%, #39328F 100%)',
                border: 'none',
                boxShadow: 'none',
                borderRadius: '8px'
              }}
            >
              <CardHeader className="px-5 py-4" style={{ paddingLeft: '20px', paddingRight: '24px', paddingTop: '16px', paddingBottom: '16px' }}>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base font-semibold" style={{ color: '#FFFFFF', letterSpacing: '0.15px', lineHeight: '24px' }}>What's Popular</CardTitle>
                  <Menu className="h-4 w-4 cursor-pointer transition-colors" style={{ color: '#FFFFFF' }} />
                </div>
              </CardHeader>
              <CardContent className="px-5 pt-0 pb-0" style={{ paddingLeft: '20px', paddingRight: '20px', paddingBottom: '20px' }}>
                <ScrollArea className="w-full">
                  <div className="flex gap-2.5">
                    {popularItems.map((item, idx) => (
                      <Card 
                        key={idx} 
                        className="min-w-[240px] cursor-pointer transition-all"
                        style={{ 
                          backgroundColor: '#0A0A0A',
                          border: '1px solid #202020',
                          borderRadius: '8px',
                          boxSizing: 'border-box'
                        }}
                      >
                        <CardContent className="p-3">
                          <div className="flex flex-col gap-2">
                            <div className="flex items-center gap-2" style={{ width: '216px' }}>
                              <div className="w-4 h-4 flex items-center justify-center flex-shrink-0">
                                <AlignEndHorizontal className="w-4 h-4" style={{ color: '#F2F2F7' }} />
                              </div>
                              <div className="flex items-center gap-2.5 flex-1 min-w-0">
                                <h3 className="font-semibold text-sm flex-1" style={{ color: '#F2F2F7', letterSpacing: '0.1px', lineHeight: '20px' }}>{item.title}</h3>
                                <svg className="w-4 h-4 flex-shrink-0" style={{ color: '#F2F2F7', opacity: 0.65 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                </svg>
                              </div>
                            </div>
                            <div className="flex flex-col gap-2.5" style={{ paddingTop: '8px' }}>
                              <p className="text-xs" style={{ color: '#FFFFFF', opacity: 0.65, letterSpacing: '0.4px', lineHeight: '16px' }}>{item.description}</p>
                              <div className="flex items-center gap-2" style={{ paddingTop: '8px' }}>
                                <div className="flex items-center gap-1 px-2 py-0.5 rounded-md" style={{ backgroundColor: '#27272A' }}>
                                  <Clock className="w-3 h-3" style={{ color: '#F2F2F7', opacity: 0.65 }} />
                                  <span className="text-xs" style={{ color: '#FAFAFA', opacity: 0.65 }}>{item.duration}</span>
                                </div>
                              </div>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>

            {/* Top News + Top Research — 随屏幕伸缩 */}
            <div className="w-full grid grid-cols-2 gap-4 flex-1 min-h-0 overflow-hidden">
              {/* Top News */}
              <Card className="fin-card flex flex-col h-full min-h-0 overflow-hidden">
                <CardHeader className="px-6 py-4 flex-shrink-0" style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base font-semibold" style={{ color: '#FFFFFF', letterSpacing: '0.15px' }}>Top News</CardTitle>
                    <Menu className="h-4 w-4 cursor-pointer transition-colors" style={{ color: '#FFFFFF' }} />
                  </div>
                </CardHeader>
                <CardContent className="px-6 pt-0 pb-0 flex-1 min-h-0 overflow-hidden" style={{ display: 'flex', flexDirection: 'column' }}>
                  <ScrollArea className="w-full flex-1 min-h-0">
                    <div className="space-y-0">
                      {newsItems.map((item, idx) => (
                        <div 
                          key={idx} 
                          className="flex items-center py-3 cursor-pointer transition-colors"
                          style={{ borderBottom: '1px solid #1F1F1F' }}
                        >
                          {item.isHot ? (
                            <>
                              {/* Icon with left margin */}
                              <div 
                                className="flex items-center justify-center mr-2 ml-1 flex-shrink-0" 
                                style={{ 
                                  padding: '2px 5px',
                                  gap: '4px',
                                  width: '22px',
                                  height: '22px',
                                  background: 'linear-gradient(0deg, rgba(108, 97, 243, 0.5), rgba(108, 97, 243, 0.5)), #27272A',
                                  borderRadius: '6px'
                                }}
                              >
                                <Sparkles className="w-3 h-3" style={{ color: '#FFFFFF' }} />
                              </div>
                              {/* Title after icon */}
                              <div className="flex-1 min-w-0">
                                <p 
                                  className="text-sm font-normal text-left" 
                                  style={{ 
                                    color: '#FFFFFF',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                    display: 'block'
                                  }}
                                  title={item.title}
                                >
                                  {item.title}
                                </p>
                              </div>
                            </>
                          ) : (
                            <>
                              {/* Title without icon - no left margin */}
                              <div className="flex-1 min-w-0">
                                <p 
                                  className="text-sm font-normal text-left" 
                                  style={{ 
                                    color: '#FFFFFF',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                    display: 'block'
                                  }}
                                  title={item.title}
                                >
                                  {item.title}
                                </p>
                              </div>
                            </>
                          )}
                          <p className="text-sm font-normal text-right flex-shrink-0 whitespace-nowrap ml-2.5" style={{ color: '#999999' }}>{item.time}</p>
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                </CardContent>
              </Card>

              {/* Top Research */}
              <Card className="fin-card flex flex-col h-full min-h-0 overflow-hidden">
                <CardHeader className="px-6 py-4 flex-shrink-0" style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base font-semibold" style={{ color: '#FFFFFF', letterSpacing: '0.15px' }}>Top Research</CardTitle>
                    <Menu className="h-4 w-4 cursor-pointer transition-colors" style={{ color: '#FFFFFF' }} />
                  </div>
                </CardHeader>
                <CardContent className="px-6 pt-0 pb-0 flex-1 min-h-0 overflow-hidden" style={{ display: 'flex', flexDirection: 'column' }}>
                  <ScrollArea className="w-full flex-1 min-h-0">
                    <div className="space-y-0">
                      {researchItems.map((item, idx) => (
                        <div 
                          key={idx} 
                          className="flex items-center gap-2.5 py-2.5 cursor-pointer transition-colors"
                          style={{ borderBottom: '1px solid #1F1F1F' }}
                        >
                          <div className="w-[90px] h-[54px] flex-shrink-0 rounded" style={{ backgroundColor: '#FFFFFF' }}>
                            {/* Placeholder for chart icon */}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-normal" style={{ color: '#FFFFFF' }}>{item.title}</p>
                          </div>
                          <p className="text-sm font-normal text-right flex-shrink-0" style={{ color: '#999999' }}>{item.time}</p>
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                </CardContent>
              </Card>
            </div>

            {/* Chat Input */}
            <Card 
              className="fin-card flex-shrink-0"
              style={{ borderColor: 'hsl(var(--primary))', borderWidth: '1.5px' }}
            >
              <CardContent className="p-3">
                <div className="flex items-center gap-1">
                  <button className="w-9 h-9 flex items-center justify-center rounded-md transition-colors">
                    <Plus className="h-4 w-4" style={{ color: '#BBBBBB' }} />
                  </button>
                  <Input 
                    placeholder="What would you like to know?" 
                    className="flex-1 h-9 rounded-md text-sm focus-visible:ring-0 focus-visible:ring-offset-0 focus:outline-none"
                    style={{ 
                      backgroundColor: 'transparent',
                      border: 'none',
                      color: '#BBBBBB',
                      fontSize: '14px',
                      outline: 'none'
                    }}
                  />
                  <div className="flex items-center gap-1">
                    <button className="flex items-center gap-1.5 px-2 py-1.5 rounded-full transition-colors">
                      <Globe className="h-4 w-4" style={{ color: '#BBBBBB' }} />
                      <span className="text-sm font-medium" style={{ color: '#BBBBBB' }}>Agent</span>
                    </button>
                    <button className="flex items-center gap-1.5 px-2 py-1.5 rounded-full transition-colors" style={{ backgroundColor: 'rgba(255, 255, 255, 0.1)' }}>
                      <Zap className="h-4 w-4" style={{ color: '#BBBBBB' }} />
                      <span className="text-sm font-medium" style={{ color: '#BBBBBB' }}>Fast</span>
                    </button>
                    <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-colors">
                      <span className="text-sm font-medium" style={{ color: '#BBBBBB' }}>Tool</span>
                      <ChevronDown className="h-4 w-4" style={{ color: '#BBBBBB' }} />
                    </button>
                    <button className="w-8 h-9 rounded-md flex items-center justify-center transition-colors" style={{ backgroundColor: '#6155F5' }}>
                      <Send className="h-4 w-4" style={{ color: '#FFFFFF' }} />
                    </button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Right Column */}
          <div className="w-full flex flex-col gap-4 h-full min-h-0 overflow-hidden">
            {/* Watchlist Panel */}
            <Card className="panel flex flex-col flex-1 min-h-0">
              <CardHeader className="px-6 py-4 flex-shrink-0">
                <button
                  type="button"
                  onClick={() => setWatchlistModalOpen(true)}
                  className="flex items-center justify-between w-full text-left"
                >
                  <CardTitle className="text-base font-semibold" style={{ color: '#FFFFFF', letterSpacing: '0.15px' }}>Create watchlist</CardTitle>
                  <Plus className="h-4 w-4 shrink-0" style={{ color: '#FFFFFF' }} />
                </button>
              </CardHeader>
              <CardContent className="px-6 pb-6 pt-0 flex-1 min-h-0">
                <ScrollArea className="h-full">
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ borderBottom: '1px solid #1F1F1F' }}>
                        <th className="text-left py-2 px-2 font-normal text-xs" style={{ color: '#999999' }}>Symbol</th>
                        <th className="text-left py-2 px-2 font-normal text-xs" style={{ color: '#999999' }}>Name</th>
                        <th className="text-left py-2 px-2 font-normal text-xs" style={{ color: '#999999' }}>Price</th>
                        <th className="text-left py-2 px-2 font-normal text-xs" style={{ color: '#999999' }}>Change</th>
                        <th className="w-8" />
                      </tr>
                    </thead>
                    <tbody>
                      {watchlistLoading
                        ? Array.from({ length: 5 }).map((_, i) => (
                            <tr key={i} style={{ borderBottom: '1px solid #1F1F1F' }}>
                              <td colSpan={5} className="py-2.5 px-2">
                                <div className="h-4 w-3/4 rounded bg-white/10 animate-pulse" />
                              </td>
                            </tr>
                          ))
                        : watchlistRows.map((item) => (
                            <tr key={item.item_id ?? item.symbol} className="transition-colors" style={{ borderBottom: '1px solid #1F1F1F' }}>
                              <td className="py-2.5 px-2 font-normal" style={{ color: '#FFFFFF' }}>{item.symbol}</td>
                              <td className="py-2.5 px-2 font-normal" style={{ color: '#FFFFFF' }}>{item.name}</td>
                              <td className="py-2.5 px-2 font-normal tabular-nums" style={{ color: item.isPositive ? '#0FEDBE' : '#FF383C' }}>
                                {Number(item.price).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                              </td>
                              <td className="py-2.5 px-2 font-normal tabular-nums" style={{ color: item.isPositive ? '#0FEDBE' : '#FF383C' }}>
                                {(item.isPositive ? '+' : '') + Number(item.changePercent).toFixed(2) + '%'}
                              </td>
                              <td className="py-2.5 px-2">
                                {item.item_id ? (
                                  <button
                                    type="button"
                                    onClick={(e) => { e.stopPropagation(); handleDeleteWatchlistItem(String(item.item_id)); }}
                                    className="p-1 rounded hover:opacity-80"
                                    style={{ color: '#999' }}
                                    aria-label="Remove"
                                  >
                                    <Trash2 className="h-4 w-4" />
                                  </button>
                                ) : null}
                              </td>
                            </tr>
                          ))}
                    </tbody>
                  </table>
                </ScrollArea>
              </CardContent>
            </Card>

            {watchlistModalOpen && (
              <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }} onClick={() => setWatchlistModalOpen(false)}>
                <div className="bg-[#1B1D25] rounded-lg shadow-xl p-6 w-full max-w-sm border border-[#2a2d38]" onClick={(e) => e.stopPropagation()}>
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-base font-semibold" style={{ color: '#FFFFFF' }}>Add stock</h3>
                    <button type="button" onClick={() => setWatchlistModalOpen(false)} className="p-1 rounded hover:opacity-80" style={{ color: '#999' }} aria-label="Close">
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                  <div className="flex gap-2">
                    <Input
                      placeholder="Symbol (e.g. AAPL)"
                      value={addSymbol}
                      onChange={(e) => setAddSymbol(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAddWatchlist(); } }}
                      className="flex-1 bg-[#0A0A0A] border-[#202020] text-white placeholder:text-gray-500"
                    />
                    <button
                      type="button"
                      onClick={handleAddWatchlist}
                      className="px-4 py-2 rounded font-medium shrink-0 hover:opacity-90"
                      style={{ backgroundColor: '#6155F5', color: '#FFFFFF' }}
                    >
                      Add
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Portfolio Panel */}
            <Card className="panel flex flex-col flex-1 min-h-0">
              <Dialog open={portfolioModalOpen} onOpenChange={setPortfolioModalOpen}>
                <CardHeader className="px-6 py-4 flex-shrink-0">
                  <button
                    type="button"
                    onClick={() => setPortfolioModalOpen(true)}
                    className="flex items-center justify-between w-full text-left"
                  >
                    <CardTitle className="text-base font-semibold" style={{ color: '#FFFFFF', letterSpacing: '0.15px' }}>Create My Portfolio</CardTitle>
                    <Plus className="h-4 w-4 shrink-0" style={{ color: '#FFFFFF' }} />
                  </button>
                </CardHeader>
                <DialogContent className="sm:max-w-sm bg-[#1B1D25] border-[#2a2d38] text-white">
                  <DialogHeader>
                    <DialogTitle style={{ color: '#FFFFFF' }}>Add holding</DialogTitle>
                  </DialogHeader>
                  <div
                    className="grid gap-3 py-2"
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAddPortfolio(); } }}
                  >
                    <div>
                      <label className="text-xs text-gray-400 block mb-1">Symbol *</label>
                      <Input
                        placeholder="e.g. AAPL"
                        value={portfolioForm.symbol}
                        onChange={(e) => setPortfolioForm((f) => ({ ...f, symbol: e.target.value }))}
                        className="bg-[#0A0A0A] border-[#202020] text-white placeholder:text-gray-500"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-gray-400 block mb-1">Quantity *</label>
                      <Input
                        type="number"
                        min="0"
                        step="any"
                        placeholder="e.g. 10.5"
                        value={portfolioForm.quantity}
                        onChange={(e) => setPortfolioForm((f) => ({ ...f, quantity: e.target.value }))}
                        className="bg-[#0A0A0A] border-[#202020] text-white placeholder:text-gray-500"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-gray-400 block mb-1">Average Cost *</label>
                      <Input
                        type="number"
                        min="0"
                        step="any"
                        placeholder="e.g. 175.50"
                        value={portfolioForm.averageCost}
                        onChange={(e) => setPortfolioForm((f) => ({ ...f, averageCost: e.target.value }))}
                        className="bg-[#0A0A0A] border-[#202020] text-white placeholder:text-gray-500"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-gray-400 block mb-1">Account Name</label>
                      <Input
                        placeholder="e.g. Robinhood"
                        value={portfolioForm.accountName}
                        onChange={(e) => setPortfolioForm((f) => ({ ...f, accountName: e.target.value }))}
                        className="bg-[#0A0A0A] border-[#202020] text-white placeholder:text-gray-500"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-gray-400 block mb-1">Notes</label>
                      <Input
                        placeholder="Optional"
                        value={portfolioForm.notes}
                        onChange={(e) => setPortfolioForm((f) => ({ ...f, notes: e.target.value }))}
                        className="bg-[#0A0A0A] border-[#202020] text-white placeholder:text-gray-500"
                      />
                    </div>
                  </div>
                  <div className="flex justify-end gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => setPortfolioModalOpen(false)}
                      className="px-3 py-1.5 rounded text-sm border border-[#202020] hover:bg-white/10"
                      style={{ color: '#FFFFFF' }}
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleAddPortfolio}
                      className="px-4 py-1.5 rounded text-sm font-medium hover:opacity-90"
                      style={{ backgroundColor: '#6155F5', color: '#FFFFFF' }}
                    >
                      Add
                    </button>
                  </div>
                </DialogContent>
              </Dialog>
              <CardContent className="px-6 pb-6 pt-0 flex-1 min-h-0">
                <ScrollArea className="h-full">
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ borderBottom: '1px solid #1F1F1F' }}>
                        <th className="text-left py-2 px-2 font-normal text-xs" style={{ color: '#999999' }}>Name / Symbol</th>
                        <th className="text-left py-2 px-2 font-normal text-xs" style={{ color: '#999999' }}>Quantity</th>
                        <th className="text-left py-2 px-2 font-normal text-xs" style={{ color: '#999999' }}>Current Price</th>
                        <th className="text-left py-2 px-2 font-normal text-xs" style={{ color: '#999999' }}>Market Value</th>
                        <th className="text-left py-2 px-2 font-normal text-xs" style={{ color: '#999999' }}>Unrealized P/L %</th>
                        {isPortfolioReal ? <th className="w-8" /> : null}
                      </tr>
                    </thead>
                    <tbody>
                      {portfolioLoading
                        ? Array.from({ length: 5 }).map((_, i) => (
                            <tr key={i} style={{ borderBottom: '1px solid #1F1F1F' }}>
                              <td colSpan={isPortfolioReal ? 6 : 5} className="py-2.5 px-2">
                                <div className="h-4 w-3/4 rounded bg-white/10 animate-pulse" />
                              </td>
                            </tr>
                          ))
                        : portfolioRows.map((row) => (
                            <tr key={row.holding_id ?? row.symbol} className="transition-colors" style={{ borderBottom: '1px solid #1F1F1F' }}>
                              <td className="py-2.5 px-2 font-normal" style={{ color: '#FFFFFF' }}>
                                <span className="block truncate" title={row.name}>{row.name}</span>
                                <span className="text-xs opacity-70">{row.symbol}</span>
                              </td>
                              <td className="py-2.5 px-2 font-normal tabular-nums" style={{ color: '#FFFFFF' }}>
                                {row.quantity != null
                                  ? Number(row.quantity).toLocaleString(undefined, { maximumFractionDigits: 4 })
                                  : '—'}
                              </td>
                              <td className="py-2.5 px-2 font-normal tabular-nums" style={{ color: '#FFFFFF' }}>
                                {Number(row.price).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                              </td>
                              <td className="py-2.5 px-2 font-normal tabular-nums" style={{ color: '#FFFFFF' }}>
                                {row.marketValue != null
                                  ? Number(row.marketValue).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                                  : '—'}
                              </td>
                              <td className="py-2.5 px-2 font-normal tabular-nums" style={{ color: row.unrealizedPlPercent != null ? (row.isPositive ? '#0FEDBE' : '#FF383C') : '#FFFFFF' }}>
                                {row.unrealizedPlPercent != null
                                  ? (row.isPositive ? '+' : '') + Number(row.unrealizedPlPercent).toFixed(2) + '%'
                                  : '—'}
                              </td>
                              {isPortfolioReal && row.holding_id ? (
                                <td className="py-2.5 px-2">
                                  <button
                                    type="button"
                                    onClick={(e) => { e.stopPropagation(); handleDeletePortfolioItem(String(row.holding_id)); }}
                                    className="p-1 rounded hover:opacity-80"
                                    style={{ color: '#999' }}
                                    aria-label="Remove"
                                  >
                                    <Trash2 className="h-4 w-4" />
                                  </button>
                                </td>
                              ) : isPortfolioReal ? <td className="py-2.5 px-2" /> : null}
                            </tr>
                          ))}
                    </tbody>
                  </table>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
