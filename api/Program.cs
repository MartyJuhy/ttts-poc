using System.Security.Claims;
using Google.Cloud.Firestore;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;
using Ttts.Api.Models;
using Ttts.Api.Services;

var builder = WebApplication.CreateBuilder(args);
var projectId = builder.Configuration["FIREBASE_PROJECT_ID"] ?? "ttts-poc";
var issuer = $"https://securetoken.google.com/{projectId}";
var adminUid = builder.Configuration["ADMIN_UID"] ?? string.Empty;
var allowedOrigins = (builder.Configuration["CORS_ORIGINS"] ?? "http://localhost:5173,http://localhost:5174,https://ttts-poc.web.app")
	.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);

builder.Services.AddCors(options => options.AddPolicy("web", policy =>
	policy.WithOrigins(allowedOrigins).AllowAnyHeader().AllowAnyMethod()));

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
	.AddJwtBearer(options =>
	{
		options.Authority = issuer;
		options.Audience = projectId;
		options.TokenValidationParameters = new TokenValidationParameters
		{
			ValidateIssuer = true,
			ValidIssuer = issuer,
			ValidateAudience = true,
			ValidAudience = projectId,
			ValidateLifetime = true,
			NameClaimType = "email",
		};
	});

builder.Services.AddAuthorization(options => options.AddPolicy("admin", policy =>
	policy.RequireAuthenticatedUser().RequireAssertion(context =>
		!string.IsNullOrWhiteSpace(adminUid) &&
		(context.User.FindFirst("user_id")?.Value == adminUid ||
		 context.User.FindFirst("sub")?.Value == adminUid ||
		 context.User.FindFirst(ClaimTypes.NameIdentifier)?.Value == adminUid))));

var useFirestore = string.Equals(builder.Configuration["DATA_PROVIDER"], "firestore", StringComparison.OrdinalIgnoreCase);
if (useFirestore)
{
	builder.Services.AddSingleton(FirestoreDb.Create(projectId));
	builder.Services.AddSingleton<IMatchStore, FirestoreMatchStore>();
}
else
{
	builder.Services.AddSingleton<IMatchStore, InMemoryMatchStore>();
}

var app = builder.Build();
app.UseCors("web");
app.UseAuthentication();
app.UseAuthorization();

app.MapGet("/api/health", () => Results.Ok(new { status = "ok" }));
app.MapGet("/api/matches", async (IMatchStore store) => Results.Ok(await store.GetMatchesAsync()));

app.MapGet("/api/admin/session", (ClaimsPrincipal user) =>
	Results.Ok(new { uid = user.FindFirst("user_id")?.Value ?? user.FindFirst(ClaimTypes.NameIdentifier)?.Value }))
	.RequireAuthorization("admin");

app.MapPost("/api/matches/{matchId}/score", async (
	string matchId,
	ScoreChangeRequest request,
	IMatchStore store) =>
{
	if (request.PlayerIndex is < 0 or > 1 || request.Delta is not (-1 or 1))
	{
		return Results.BadRequest(new { error = "PlayerIndex must be 0 or 1 and delta must be -1 or 1." });
	}

	var result = await store.ChangePointsAsync(matchId, request);
	return result.Failure switch
	{
		ScoreChangeFailure.NotFound => Results.NotFound(new { error = "Match not found." }),
		ScoreChangeFailure.Conflict => Results.Conflict(new { error = "The score changed. Refresh and try again." }),
		ScoreChangeFailure.NegativeScore => Results.BadRequest(new { error = "Score cannot be negative." }),
		ScoreChangeFailure.MatchNotLive => Results.Conflict(new { error = "Match is no longer live." }),
		_ => Results.Ok(result.Match),
	};
}).RequireAuthorization("admin");

app.Run();
