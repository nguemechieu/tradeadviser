import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './Community.css';

interface CommunityUser {
  id: string;
  name: string;
  avatar: string;
  role: string;
  followers: number;
  isFollowing: boolean;
}

interface CommunityPost {
  id: string;
  author: string;
  avatar: string;
  role: string;
  content: string;
  timestamp: string;
  likes: number;
  replies: number;
  tags: string[];
  liked: boolean;
}

const Community: React.FC = () => {
  const navigate = useNavigate();
  const [posts, setPosts] = useState<CommunityPost[]>([
    {
      id: '1',
      author: 'Alice Johnson',
      avatar: '👩‍💼',
      role: 'Expert Trader',
      content: 'Just completed a successful swing trade on AAPL. The momentum indicators were perfectly aligned today!',
      timestamp: '2 hours ago',
      likes: 145,
      replies: 23,
      tags: ['swing-trade', 'technical-analysis', 'apple'],
      liked: false,
    },
    {
      id: '2',
      author: 'Bob Chen',
      avatar: '👨‍💻',
      role: 'Risk Manager',
      content: 'New risk management strategy: Portfolio heat mapping. Who else uses this technique?',
      timestamp: '4 hours ago',
      likes: 89,
      replies: 15,
      tags: ['risk-management', 'strategy', 'portfolio'],
      liked: false,
    },
    {
      id: '3',
      author: 'Sarah Williams',
      avatar: '👩‍🔬',
      role: 'Quant Researcher',
      content: 'Released my new backtesting framework on GitHub. Open source and free for all traders!',
      timestamp: '6 hours ago',
      likes: 203,
      replies: 42,
      tags: ['backtesting', 'open-source', 'tools'],
      liked: false,
    },
  ]);

  const [topMembers] = useState<CommunityUser[]>([
    {
      id: '1',
      name: 'Alex Martinez',
      avatar: '👨‍🏫',
      role: 'Trading Coach',
      followers: 2543,
      isFollowing: false,
    },
    {
      id: '2',
      name: 'Emma Davis',
      avatar: '📊',
      role: 'Data Scientist',
      followers: 1876,
      isFollowing: false,
    },
    {
      id: '3',
      name: 'James Wilson',
      avatar: '🎯',
      role: 'Portfolio Manager',
      followers: 1654,
      isFollowing: false,
    },
  ]);

  const [newPost, setNewPost] = useState('');
  const [activeTab, setActiveTab] = useState<'feed' | 'trending' | 'members'>('feed');

  const handleToggleLike = (postId: string) => {
    setPosts(posts.map(post => 
      post.id === postId 
        ? { ...post, liked: !post.liked, likes: post.liked ? post.likes - 1 : post.likes + 1 }
        : post
    ));
  };

  const handlePostSubmit = () => {
    if (newPost.trim()) {
      const post: CommunityPost = {
        id: Date.now().toString(),
        author: 'You',
        avatar: '👤',
        role: 'Trader',
        content: newPost,
        timestamp: 'now',
        likes: 0,
        replies: 0,
        tags: [],
        liked: false,
      };
      setPosts([post, ...posts]);
      setNewPost('');
    }
  };

  const trendingTopics = [
    { tag: 'swing-trading', posts: 342 },
    { tag: 'ai-strategies', posts: 289 },
    { tag: 'risk-management', posts: 267 },
    { tag: 'portfolio-optimization', posts: 245 },
    { tag: 'market-analysis', posts: 198 },
    { tag: 'cryptocurrency', posts: 176 },
  ];

  return (
    <section className="community">
      {/* Header */}
      <div className="community-header">
        <div className="header-content">
          <h1>Trading Community</h1>
          <p>Connect, share, and learn from thousands of traders worldwide</p>
        </div>
        <div className="header-stats">
          <div className="stat">
            <span className="stat-value">15,842</span>
            <span className="stat-label">Members</span>
          </div>
          <div className="stat">
            <span className="stat-value">3,256</span>
            <span className="stat-label">Daily Posts</span>
          </div>
          <div className="stat">
            <span className="stat-value">98%</span>
            <span className="stat-label">Engagement</span>
          </div>
        </div>
      </div>

      <div className="community-container">
        {/* Sidebar */}
        <aside className="community-sidebar">
          <div className="sidebar-section">
            <h3>Categories</h3>
            <nav className="category-nav">
              <a href="#" className="category-link active">📊 Strategies</a>
              <a href="#" className="category-link">📈 Technical Analysis</a>
              <a href="#" className="category-link">💼 Risk Management</a>
              <a href="#" className="category-link">🎓 Learning</a>
              <a href="#" className="category-link">🤖 AI & Automation</a>
              <a href="#" className="category-link">💬 General Discussion</a>
            </nav>
          </div>

          <div className="sidebar-section">
            <h3>Trending Topics</h3>
            <div className="trending-topics">
              {trendingTopics.map((topic) => (
                <a key={topic.tag} href="#" className="trending-tag">
                  <span className="tag-name">#{topic.tag}</span>
                  <span className="tag-count">{topic.posts}</span>
                </a>
              ))}
            </div>
          </div>

          <div className="sidebar-section">
            <h3>Rules</h3>
            <ul className="rules-list">
              <li>Be respectful and professional</li>
              <li>No spam or self-promotion</li>
              <li>Share knowledge freely</li>
              <li>Ask questions responsibly</li>
              <li>Verify before trusting advice</li>
            </ul>
          </div>
        </aside>

        {/* Main Content */}
        <main className="community-main">
          {/* Navigation Tabs */}
          <div className="tabs-navigation">
            <button
              className={`tab ${activeTab === 'feed' ? 'active' : ''}`}
              onClick={() => setActiveTab('feed')}
            >
              📰 Feed
            </button>
            <button
              className={`tab ${activeTab === 'trending' ? 'active' : ''}`}
              onClick={() => setActiveTab('trending')}
            >
              🔥 Trending
            </button>
            <button
              className={`tab ${activeTab === 'members' ? 'active' : ''}`}
              onClick={() => setActiveTab('members')}
            >
              👥 Top Members
            </button>
          </div>

          {/* Create Post */}
          <div className="create-post-section">
            <div className="post-avatar">💬</div>
            <div className="post-input-wrapper">
              <textarea
                className="post-input"
                placeholder="Share your trading insights, ask questions, or discuss strategies..."
                value={newPost}
                onChange={(e) => setNewPost(e.target.value)}
              />
              <div className="post-actions">
                <button className="post-btn-secondary">📎 Attach</button>
                <button
                  className="post-btn-primary"
                  onClick={handlePostSubmit}
                  disabled={!newPost.trim()}
                >
                  Post
                </button>
              </div>
            </div>
          </div>

          {/* Feed Tab */}
          {activeTab === 'feed' && (
            <div className="posts-feed">
              {posts.map((post) => (
                <div key={post.id} className="post-card">
                  <div className="post-header">
                    <div className="post-author">
                      <div className="author-avatar">{post.avatar}</div>
                      <div className="author-info">
                        <h4 className="author-name">{post.author}</h4>
                        <span className="author-role">{post.role}</span>
                      </div>
                    </div>
                    <span className="post-timestamp">{post.timestamp}</span>
                  </div>

                  <div className="post-content">
                    <p>{post.content}</p>
                    {post.tags.length > 0 && (
                      <div className="post-tags">
                        {post.tags.map((tag) => (
                          <a key={tag} href="#" className="post-tag">
                            #{tag}
                          </a>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="post-footer">
                    <button
                      className={`post-action ${post.liked ? 'liked' : ''}`}
                      onClick={() => handleToggleLike(post.id)}
                    >
                      <span className="action-icon">👍</span>
                      <span className="action-count">{post.likes}</span>
                    </button>
                    <button className="post-action">
                      <span className="action-icon">💬</span>
                      <span className="action-count">{post.replies}</span>
                    </button>
                    <button className="post-action">
                      <span className="action-icon">📤</span>
                      <span>Share</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Trending Tab */}
          {activeTab === 'trending' && (
            <div className="trending-section">
              <div className="trending-grid">
                {trendingTopics.map((topic) => (
                  <div key={topic.tag} className="trending-card">
                    <div className="trending-icon">🔥</div>
                    <h4>{topic.tag.replace('-', ' ')}</h4>
                    <p>{topic.posts} posts today</p>
                    <button className="btn-explore">Explore</button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Members Tab */}
          {activeTab === 'members' && (
            <div className="members-section">
              <div className="members-grid">
                {topMembers.map((member) => (
                  <div key={member.id} className="member-card">
                    <div className="member-avatar">{member.avatar}</div>
                    <h4 className="member-name">{member.name}</h4>
                    <p className="member-role">{member.role}</p>
                    <p className="member-followers">👥 {member.followers.toLocaleString()} followers</p>
                    <button className="btn-follow">Follow</button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </main>

        {/* Right Sidebar - Top Members */}
        <aside className="community-right-sidebar">
          <div className="sidebar-section">
            <h3>Top Contributors</h3>
            <div className="contributors-list">
              {topMembers.map((member) => (
                <div key={member.id} className="contributor-item">
                  <div className="contributor-avatar">{member.avatar}</div>
                  <div className="contributor-info">
                    <h4>{member.name}</h4>
                    <p>{member.role}</p>
                  </div>
                  <div className="contributor-followers">{member.followers}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="sidebar-section">
            <h3>Community Badges</h3>
            <div className="badges-grid">
              <div className="badge">
                <span className="badge-icon">🏆</span>
                <span className="badge-name">Expert</span>
              </div>
              <div className="badge">
                <span className="badge-icon">⭐</span>
                <span className="badge-name">Star</span>
              </div>
              <div className="badge">
                <span className="badge-icon">📚</span>
                <span className="badge-name">Scholar</span>
              </div>
              <div className="badge">
                <span className="badge-icon">🚀</span>
                <span className="badge-name">Rising Star</span>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
};

export default Community;
