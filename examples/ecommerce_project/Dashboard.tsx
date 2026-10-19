import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './Dashboard.css';

// TypeScript interfaces for type safety
interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

interface Product {
  id: number;
  name: string;
  sku: string;
  price: number;
  status: string;
  inventory_quantity: number;
  category_id: number;
  brand?: string;
}

interface Order {
  id: number;
  order_number: string;
  user_id: number;
  status: string;
  total_amount: number;
  customer_email: string;
  created_at: string;
  items: OrderItem[];
}

interface OrderItem {
  id: number;
  product_name: string;
  quantity: number;
  unit_price: number;
  total_price: number;
}

interface Notification {
  id: number;
  type: string;
  category: string;
  subject?: string;
  message: string;
  created_at: string;
  read_at?: string;
}

interface DashboardStats {
  total_users: number;
  total_products: number;
  total_orders: number;
  pending_orders: number;
  total_revenue: number;
  unread_notifications: number;
}

// API service class
class ApiService {
  private baseURL: string;

  constructor(baseURL: string = 'http://localhost:8000') {
    this.baseURL = baseURL;
  }

  // Authentication endpoints
  async login(email: string, password: string): Promise<{ access_token: string; user: User }> {
    const response = await axios.post(`${this.baseURL}/auth/login`, {
      email,
      password
    });
    return response.data;
  }

  async signup(userData: {
    email: string;
    password: string;
    first_name: string;
    last_name: string;
  }): Promise<User> {
    const response = await axios.post(`${this.baseURL}/auth/signup`, userData);
    return response.data;
  }

  async verifyToken(token: string): Promise<{ valid: boolean; user_id: string; role: string }> {
    const response = await axios.get(`${this.baseURL}/auth/verify`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  }

  // Product endpoints
  async getProducts(filters?: {
    category_id?: number;
    min_price?: number;
    max_price?: number;
    in_stock_only?: boolean;
  }): Promise<Product[]> {
    const response = await axios.get(`${this.baseURL}/products`, {
      params: filters
    });
    return response.data;
  }

  async createProduct(productData: {
    name: string;
    sku: string;
    price: number;
    category_id: number;
    description?: string;
  }): Promise<Product> {
    const response = await axios.post(`${this.baseURL}/products`, productData);
    return response.data;
  }

  async updateInventory(productId: number, quantity: number): Promise<void> {
    await axios.put(`${this.baseURL}/inventory/${productId}`, {
      quantity_available: quantity
    });
  }

  // Order endpoints
  async getOrders(userId?: number): Promise<Order[]> {
    const response = await axios.get(`${this.baseURL}/orders`, {
      params: userId ? { user_id: userId } : {}
    });
    return response.data;
  }

  async createOrder(orderData: {
    user_id: number;
    items: Array<{ product_id: number; quantity: number }>;
    customer_email: string;
    shipping_address: any;
  }): Promise<Order> {
    const response = await axios.post(`${this.baseURL}/orders`, orderData);
    return response.data;
  }

  async updateOrderStatus(orderId: number, status: string, reason?: string): Promise<Order> {
    const response = await axios.put(`${this.baseURL}/orders/${orderId}/status`, {
      status,
      reason
    });
    return response.data;
  }

  // Notification endpoints
  async getUserNotifications(userId: number, unreadOnly: boolean = false): Promise<Notification[]> {
    const response = await axios.get(`${this.baseURL}/notifications/user/${userId}`, {
      params: { unread_only: unreadOnly }
    });
    return response.data;
  }

  async markNotificationRead(notificationId: number, userId: number): Promise<void> {
    await axios.put(`${this.baseURL}/notifications/${notificationId}/read`, {
      user_id: userId
    });
  }

  async sendNotification(notificationData: {
    user_id: number;
    type: string;
    category: string;
    message: string;
    recipient_email?: string;
  }): Promise<Notification> {
    const response = await axios.post(`${this.baseURL}/notifications`, notificationData);
    return response.data;
  }

  // Dashboard stats
  async getDashboardStats(): Promise<DashboardStats> {
    // Mock implementation - in real app, this would be a dedicated endpoint
    const [users, products, orders] = await Promise.all([
      this.getUsers(),
      this.getProducts(),
      this.getOrders()
    ]);

    const pendingOrders = orders.filter(order => order.status === 'pending').length;
    const totalRevenue = orders.reduce((sum, order) => sum + order.total_amount, 0);

    return {
      total_users: users.length,
      total_products: products.length,
      total_orders: orders.length,
      pending_orders: pendingOrders,
      total_revenue: totalRevenue,
      unread_notifications: 0 // Would come from notifications endpoint
    };
  }

  private async getUsers(): Promise<User[]> {
    // Mock implementation - would be a real endpoint
    return [];
  }
}

// Main Dashboard Component
const Dashboard: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  const api = new ApiService();

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      
      // Load dashboard statistics
      const statsData = await api.getDashboardStats();
      setStats(statsData);

      // Load recent products
      const productsData = await api.getProducts();
      setProducts(productsData.slice(0, 5)); // Show only 5 recent products

      // Load recent orders
      const ordersData = await api.getOrders();
      setOrders(ordersData.slice(0, 5)); // Show only 5 recent orders

      // Load notifications if user is logged in
      if (user) {
        const notificationsData = await api.getUserNotifications(user.id);
        setNotifications(notificationsData.slice(0, 5)); // Show only 5 recent notifications
      }

    } catch (error) {
      console.error('Failed to load dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (email: string, password: string) => {
    try {
      const loginData = await api.login(email, password);
      setUser(loginData.user);
      localStorage.setItem('access_token', loginData.access_token);
      await loadDashboardData();
    } catch (error) {
      console.error('Login failed:', error);
      alert('Login failed. Please check your credentials.');
    }
  };

  const handleLogout = () => {
    setUser(null);
    localStorage.removeItem('access_token');
    setStats(null);
    setProducts([]);
    setOrders([]);
    setNotifications([]);
  };

  const handleMarkNotificationRead = async (notificationId: number) => {
    if (!user) return;
    
    try {
      await api.markNotificationRead(notificationId, user.id);
      setNotifications(prev => 
        prev.map(notif => 
          notif.id === notificationId 
            ? { ...notif, read_at: new Date().toISOString() }
            : notif
        )
      );
    } catch (error) {
      console.error('Failed to mark notification as read:', error);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return (
      <div className="dashboard-loading">
        <div className="spinner"></div>
        <p>Loading dashboard...</p>
      </div>
    );
  }

  if (!user) {
    return <LoginForm onLogin={handleLogin} />;
  }

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>E-Commerce Dashboard</h1>
        <div className="user-info">
          <span>Welcome, {user.first_name}!</span>
          <button onClick={handleLogout} className="logout-btn">Logout</button>
        </div>
      </header>

      <nav className="dashboard-nav">
        <button 
          className={activeTab === 'overview' ? 'active' : ''}
          onClick={() => setActiveTab('overview')}
        >
          Overview
        </button>
        <button 
          className={activeTab === 'products' ? 'active' : ''}
          onClick={() => setActiveTab('products')}
        >
          Products
        </button>
        <button 
          className={activeTab === 'orders' ? 'active' : ''}
          onClick={() => setActiveTab('orders')}
        >
          Orders
        </button>
        <button 
          className={activeTab === 'notifications' ? 'active' : ''}
          onClick={() => setActiveTab('notifications')}
        >
          Notifications
        </button>
      </nav>

      <main className="dashboard-content">
        {activeTab === 'overview' && (
          <OverviewTab stats={stats} />
        )}
        
        {activeTab === 'products' && (
          <ProductsTab products={products} />
        )}
        
        {activeTab === 'orders' && (
          <OrdersTab orders={orders} />
        )}
        
        {activeTab === 'notifications' && (
          <NotificationsTab 
            notifications={notifications}
            onMarkRead={handleMarkNotificationRead}
          />
        )}
      </main>
    </div>
  );
};

// Login Form Component
const LoginForm: React.FC<{ onLogin: (email: string, password: string) => void }> = ({ onLogin }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onLogin(email, password);
  };

  return (
    <div className="login-form">
      <h2>Login to Dashboard</h2>
      <form onSubmit={handleSubmit}>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <button type="submit">Login</button>
      </form>
    </div>
  );
};

// Overview Tab Component
const OverviewTab: React.FC<{ stats: DashboardStats | null }> = ({ stats }) => {
  if (!stats) return <div>Loading stats...</div>;

  return (
    <div className="overview-tab">
      <h2>Dashboard Overview</h2>
      <div className="stats-grid">
        <div className="stat-card">
          <h3>Total Users</h3>
          <p className="stat-number">{stats.total_users}</p>
        </div>
        <div className="stat-card">
          <h3>Total Products</h3>
          <p className="stat-number">{stats.total_products}</p>
        </div>
        <div className="stat-card">
          <h3>Total Orders</h3>
          <p className="stat-number">{stats.total_orders}</p>
        </div>
        <div className="stat-card">
          <h3>Pending Orders</h3>
          <p className="stat-number">{stats.pending_orders}</p>
        </div>
        <div className="stat-card">
          <h3>Total Revenue</h3>
          <p className="stat-number">${stats.total_revenue.toFixed(2)}</p>
        </div>
        <div className="stat-card">
          <h3>Unread Notifications</h3>
          <p className="stat-number">{stats.unread_notifications}</p>
        </div>
      </div>
    </div>
  );
};

// Products Tab Component
const ProductsTab: React.FC<{ products: Product[] }> = ({ products }) => {
  return (
    <div className="products-tab">
      <h2>Recent Products</h2>
      <div className="products-table">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>SKU</th>
              <th>Price</th>
              <th>Status</th>
              <th>Inventory</th>
            </tr>
          </thead>
          <tbody>
            {products.map(product => (
              <tr key={product.id}>
                <td>{product.name}</td>
                <td>{product.sku}</td>
                <td>${product.price}</td>
                <td className={`status ${product.status}`}>{product.status}</td>
                <td>{product.inventory_quantity || 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// Orders Tab Component
const OrdersTab: React.FC<{ orders: Order[] }> = ({ orders }) => {
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  return (
    <div className="orders-tab">
      <h2>Recent Orders</h2>
      <div className="orders-table">
        <table>
          <thead>
            <tr>
              <th>Order #</th>
              <th>Customer</th>
              <th>Status</th>
              <th>Total</th>
              <th>Date</th>
            </tr>
          </thead>
          <tbody>
            {orders.map(order => (
              <tr key={order.id}>
                <td>{order.order_number}</td>
                <td>{order.customer_email}</td>
                <td className={`status ${order.status}`}>{order.status}</td>
                <td>{formatCurrency(order.total_amount)}</td>
                <td>{formatDate(order.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// Notifications Tab Component
const NotificationsTab: React.FC<{ 
  notifications: Notification[];
  onMarkRead: (id: number) => void;
}> = ({ notifications, onMarkRead }) => {
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div className="notifications-tab">
      <h2>Recent Notifications</h2>
      <div className="notifications-list">
        {notifications.map(notification => (
          <div 
            key={notification.id} 
            className={`notification-item ${notification.read_at ? 'read' : 'unread'}`}
            onClick={() => !notification.read_at && onMarkRead(notification.id)}
          >
            <div className="notification-header">
              <span className="notification-type">{notification.type}</span>
              <span className="notification-date">{formatDate(notification.created_at)}</span>
            </div>
            {notification.subject && (
              <h4 className="notification-subject">{notification.subject}</h4>
            )}
            <p className="notification-message">{notification.message}</p>
            <div className="notification-meta">
              <span className="notification-category">{notification.category}</span>
              {!notification.read_at && <span className="unread-indicator">•</span>}
            </div>
          </div>
        ))}
        {notifications.length === 0 && (
          <p className="no-notifications">No notifications found.</p>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
