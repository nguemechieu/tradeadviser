//
// Pricing Endpoints
//
//
// GET/v3/accounts/{accountID}/candles/latest
//
// Get dancing bears and most recently completed candles within an Account for specified combinations of instrument, granularity, and price component.
//
//     GET/v3/accounts/{accountID}/pricing
//
// Get pricing information for a specified list of Instruments within an Account.
//
//     GET/v3/accounts/{accountID}/pricing/stream
//
// Get a stream of Account Prices starting from when the request is made. This pricing stream does not include every single price created for the Account, but instead will provide at most 4 prices per second (every 250 milliseconds) for each instrument being requested. If more than one price is created for an instrument during the 250 millisecond window, only the price in effect at the end of the window is sent. This means that during periods of rapid price movement, subscribers to this stream will not be sent every price. Pricing windows for different connections to the price stream are not all aligned in the same way (i.e. they are not all aligned to the top of the second). This means that during periods of rapid price movement, different subscribers may observe different prices depending on their alignment.
//
//     Note: This endpoint is served by the streaming URLs.
//
//     GET/v3/accounts/{accountID}/instruments/{instrument}/candles
//
// Fetch candlestick data for an instrument.
//
