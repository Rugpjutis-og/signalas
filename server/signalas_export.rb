# frozen_string_literal: true
# Run by the pod administrator INSIDE the Diaspora Rails installation.
# Prefer a SELECT-only database role or a read replica. Never expose this as a public route.
require "json"
require "optparse"
require "tempfile"
require "uri"
require "time"

options = {batch_size: 500, from: ENV["SIGNALAS_FROM"] && Time.iso8601(ENV["SIGNALAS_FROM"]),
           until: ENV["SIGNALAS_UNTIL"] && Time.iso8601(ENV["SIGNALAS_UNTIL"]),
           base_url: ENV["SIGNALAS_BASE_URL"], output: ENV["SIGNALAS_OUTPUT"],
           exercise_id: ENV["SIGNALAS_EXERCISE_ID"]}
OptionParser.new do |parser|
  parser.on("--from ISO8601") {|value| options[:from] = Time.iso8601(value) }
  parser.on("--until ISO8601") {|value| options[:until] = Time.iso8601(value) }
  parser.on("--base-url URL") {|value| options[:base_url] = value }
  parser.on("--output FILE") {|value| options[:output] = value }
  parser.on("--exercise-id ID") {|value| options[:exercise_id] = value }
end.parse!(ARGV)
abort "Required: --from, --until, --base-url, --output" unless
  %i[from until base_url output].all? {|name| options[name] }
abort "The end must follow the start" unless options[:until] > options[:from]
base = URI.parse(options[:base_url])
abort "Expected an HTTPS pod origin" unless base.scheme == "https" && base.host &&
  ["", "/"].include?(base.path) && !base.userinfo && !base.query && !base.fragment
abort "This exporter requires PostgreSQL and an existing Rails environment" unless
  defined?(ActiveRecord::Base) && ActiveRecord::Base.connection.adapter_name.downcase.include?("postgres")

output = File.expand_path(options[:output])
abort "Refusing to overwrite an existing export" if File.exist?(output)
window = options[:from]...options[:until]
types = ["StatusMessage", "Reshare"]
routes = Rails.application.routes.url_helpers
supported = Post.where(type: types)
window_posts = supported.where(created_at: window)
# Comments are selected independently: their parent may predate the requested window.
window_comments = Comment.where(commentable_type: "Post", created_at: window)
                         .where(commentable_id: supported.select(:id))
parents = supported.where(id: window_posts.select(:id))
                   .or(supported.where(id: window_comments.select(:commentable_id)))

ActiveRecord::Base.transaction(isolation: :repeatable_read) do
  ActiveRecord::Base.connection.execute("SET TRANSACTION READ ONLY")
  Tempfile.create(["signalas-", ".json"], File.dirname(output)) do |file|
    file.chmod(0600)
    file.set_encoding("UTF-8")
    file.write('{"format":"signalas.diaspora.export.v1","raw_posts":[')
    first = true
    exported_posts = 0
    exported_comments = 0
    parents.find_each(batch_size: options[:batch_size]) do |post|
      # Model/presenter reads only: no post service, notifications, or user feed.
      raw = PostPresenter.new(post, nil).with_interactions.as_json.deep_symbolize_keys
      # The normal comment presenter contains only the viewer's own likes.
      # A server-authorized export explicitly reads all comment interactions.
      raw[:interactions][:comments] = post.comments.order(:created_at, :id).map do |comment|
        item = CommentPresenter.new(comment, nil).as_json
        item[:interactions] = {
          likes: comment.likes.includes(author: :profile).map {|like| like.as_api_response(:backbone) },
          likes_count: comment.likes.count
        }
        item
      end
      raw[:interactions][:comments_count] = post.comments.count
      raw[:interactions][:likes_count] = post.likes.count
      raw[:interactions][:reshares_count] = post.reshares.count
      url = routes.post_url(post, host: base.host, port: base.port == 443 ? nil : base.port, protocol: "https")
      in_window = window.cover?(post.created_at)
      exported_posts += 1 if in_window
      exported_comments += post.comments.where(created_at: window).count
      file.write(",") unless first
      first = false
      file.write({post: raw, sourceUrl: url, context_only: !in_window}.to_json)
    end
    scope = {
      kind: "pod_database", source: options[:base_url].sub(%r{/$}, ""),
      from: options[:from].utc.iso8601, until: options[:until].utc.iso8601,
      includes_private: true, contact_filter: false, membership_filter: false,
      complete: exported_posts == window_posts.count && exported_comments == window_comments.count,
      expected_posts: window_posts.count, expected_comments: window_comments.count,
      exported_posts: exported_posts, exported_comments: exported_comments,
      post_types: types, declared_by: "server_administrator",
      database_read_only: true, exercise_id: options[:exercise_id]
    }
    file.write('],"scope":' + scope.to_json + ',"collected_at":' + Time.now.utc.iso8601.to_json + "}")
    file.flush
    file.fsync
    File.rename(file.path, output)
  end
end
puts "Read-only export completed: #{output}"
